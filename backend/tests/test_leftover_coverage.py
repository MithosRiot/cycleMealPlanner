from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _setup_source(client: TestClient, suffix: str) -> tuple[dict, dict, int, int]:
    units = {item["code"]: item for item in client.get("/api/reference/units").json()}
    each = units["each"]
    refrigerator = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Refrigerator")
    pantry = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Pantry")
    ingredient = client.post("/api/ingredients", json={
        "name": f"Coverage Ingredient {suffix}", "shopping_category_id": None,
        "preferred_unit_id": each["id"], "default_location_id": pantry["id"],
        "perishable": False, "notes": None, "aliases": [],
    }).json()
    client.post("/api/inventory", json={
        "ingredient_id": ingredient["id"], "location_id": pantry["id"], "quantity": "10",
        "unit_id": each["id"], "purchase_date": "2026-09-01", "opened_date": None,
        "expiration_date": None, "frozen_date": None, "thawed_date": None, "notes": None,
        "transaction_type": "MANUAL_ADD",
    }).raise_for_status()
    recipe = client.post("/api/recipes", json={
        "name": f"Coverage Recipe {suffix}", "description": None, "base_servings": "4",
        "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
        "prep_time_minutes": 5, "cook_time_minutes": 10, "notes": None, "favorite": False,
        "meal_types": ["DINNER"], "tag_ids": [], "prep_groups": [], "advance_prep": [], "equipment": [],
        "ingredients": [{
            "ingredient_id": ingredient["id"], "prep_group_key": None, "quantity": "1", "unit_id": each["id"],
            "display_text": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None,
            "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0,
            "notes": None, "substitutions": [],
        }],
    }).json()
    meal = client.post("/api/meals", json={
        "name": f"Coverage Meal {suffix}", "description": None, "favorite": False,
        "meal_types": ["DINNER"], "tag_ids": [],
        "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
    }).json()
    cycle = client.post("/api/meal-cycles", json={
        "name": f"Coverage Cycle {suffix}", "duration_days": 2, "start_date": "2026-09-05", "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
    }).json()
    slots = sorted(cycle["slots"], key=lambda row: row["day_number"])
    source = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slots[0]['id']}/planned-meal", json={"meal_id": meal["id"]}).json()
    updated = client.put(f"/api/meal-cycles/{cycle['id']}/slots/{slots[0]['id']}/planned-meal/planning", json={
        "planned_servings": "4", "planned_leftover_servings": "2", "component_serving_overrides": {},
    })
    assert updated.status_code == 200
    return source, cycle, slots[1]["id"], refrigerator["id"]


def _finalize_source(client: TestClient, source_id: int) -> None:
    draft = client.post(f"/api/planned-meals/{source_id}/completion")
    assert draft.status_code == 200
    finalized = client.post(f"/api/planned-meals/{source_id}/completion/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["completion"]["status"] == "FINALIZED"


def _commit_leftovers(client: TestClient, source_id: int, refrigerator_id: int, produced: str, eaten: str) -> dict:
    committed = client.post(f"/api/planned-meals/{source_id}/completion/production", json={
        "actual_servings_produced": produced,
        "actual_servings_eaten": eaten,
        "leftover_location_id": refrigerator_id,
        "leftover_expiration_date": "2026-09-10",
        "leftover_notes": "coverage test",
        "outputs": [],
    })
    assert committed.status_code == 200
    return committed.json()


def test_finalization_releases_ingredient_reservations_and_shortage_reconciles() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        source, cycle, future_slot_id, refrigerator_id = _setup_source(client, suffix)
        before = client.get(f"/api/meal-cycles/{cycle['id']}/reservations").json()
        source_rows = [row for row in before["reservations"] if row["planned_meal_id"] == source["id"]]
        assert source_rows and all(row["status"] == "ACTIVE" for row in source_rows)

        _finalize_source(client, source["id"])
        released = client.get(f"/api/meal-cycles/{cycle['id']}/reservations").json()
        source_rows = [row for row in released["reservations"] if row["planned_meal_id"] == source["id"]]
        assert source_rows and all(row["status"] == "RELEASED" for row in source_rows)

        regenerated = client.post(f"/api/meal-cycles/{cycle['id']}/reservations/regenerate").json()
        source_rows = [row for row in regenerated["reservations"] if row["planned_meal_id"] == source["id"]]
        assert source_rows and all(row["status"] == "RELEASED" for row in source_rows)

        options = client.get("/api/produced-source-options").json()
        leftover_option = next(row for row in options if row["source_type"] == "LEFTOVER" and row["source_origin_planned_meal_id"] == source["id"])
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{future_slot_id}/planned-source", json={
            "source_type": "LEFTOVER", "source_origin_planned_meal_id": source["id"],
            "source_record_id": leftover_option["source_record_id"], "source_recipe_output_id": None,
            "quantity": "2", "unit_id": leftover_option["unit_id"],
        })
        assert placed.status_code == 201
        future = placed.json()

        coverage = client.get(f"/api/meal-cycles/{cycle['id']}/production-coverage").json()
        row = next(item for item in coverage["reservations"] if item["planned_meal_id"] == future["id"] and item["status"] == "ACTIVE")
        assert Decimal(row["reserved_quantity"]) == Decimal("0")
        assert Decimal(row["shortage_quantity"]) == Decimal("2")

        produced = _commit_leftovers(client, source["id"], refrigerator_id, "5", "4")
        leftover_lot_id = produced["leftover"]["inventory_lot_id"]
        coverage = client.get(f"/api/meal-cycles/{cycle['id']}/production-coverage").json()
        row = next(item for item in coverage["reservations"] if item["planned_meal_id"] == future["id"] and item["status"] == "ACTIVE")
        assert row["lot_id"] == leftover_lot_id
        assert Decimal(row["reserved_quantity"]) == Decimal("1")
        assert Decimal(row["shortage_quantity"]) == Decimal("1")

        availability = client.get("/api/production-inventory-availability").json()
        lot = next(item for item in availability if item["lot_id"] == leftover_lot_id)
        assert Decimal(lot["physical_quantity"]) == Decimal("1")
        assert Decimal(lot["reserved_quantity"]) == Decimal("1")
        assert Decimal(lot["available_quantity"]) == Decimal("0")

        validation = client.get(f"/api/meal-cycles/{cycle['id']}/validate").json()
        shortages = [item for item in validation["issues"] if item["code"] == "LEFTOVER_COVERAGE_SHORTAGE"]
        assert len(shortages) == 1
        assert shortages[0]["context"]["planned_meal_id"] == future["id"]
        assert shortages[0]["context"]["shortage_quantity"] == "1.000000"


def test_excess_leftovers_remain_available_and_removal_releases_only_coverage() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        source, cycle, future_slot_id, refrigerator_id = _setup_source(client, suffix)
        _finalize_source(client, source["id"])
        option = next(row for row in client.get("/api/produced-source-options").json() if row["source_type"] == "LEFTOVER" and row["source_origin_planned_meal_id"] == source["id"])
        future = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{future_slot_id}/planned-source", json={
            "source_type": "LEFTOVER", "source_origin_planned_meal_id": source["id"],
            "source_record_id": option["source_record_id"], "source_recipe_output_id": None,
            "quantity": "2", "unit_id": option["unit_id"],
        }).json()
        produced = _commit_leftovers(client, source["id"], refrigerator_id, "7", "4")
        lot_id = produced["leftover"]["inventory_lot_id"]

        availability = next(row for row in client.get("/api/production-inventory-availability").json() if row["lot_id"] == lot_id)
        assert Decimal(availability["physical_quantity"]) == Decimal("3")
        assert Decimal(availability["reserved_quantity"]) == Decimal("2")
        assert Decimal(availability["available_quantity"]) == Decimal("1")

        blocked = client.post(f"/api/inventory/{lot_id}/remove", json={"quantity": "2", "note": "must not consume reserved future stock"})
        assert blocked.status_code == 409

        removed = client.delete(f"/api/meal-cycles/{cycle['id']}/slots/{future_slot_id}/planned-meal")
        assert removed.status_code == 204
        coverage = client.get(f"/api/meal-cycles/{cycle['id']}/production-coverage").json()
        historical = [row for row in coverage["reservations"] if row["planned_meal_id"] == future["id"]]
        assert historical and all(row["status"] == "RELEASED" for row in historical)

        availability = next(row for row in client.get("/api/production-inventory-availability").json() if row["lot_id"] == lot_id)
        assert Decimal(availability["reserved_quantity"]) == Decimal("0")
        assert Decimal(availability["available_quantity"]) == Decimal("3")
