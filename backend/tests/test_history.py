from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_completed_meal(client: TestClient, suffix: str) -> dict:
    units = {item["code"]: item for item in client.get("/api/reference/units").json()}
    each = units["each"]
    ounce = units["oz"]
    locations = client.get("/api/reference/inventory-locations").json()
    pantry = next(item for item in locations if item["name"] == "Pantry")
    history_location_response = client.post("/api/reference/inventory-locations", json={
        "name": f"History Test Location {suffix}",
        "parent_location_id": None,
        "location_type": "OTHER",
        "sort_order": 900,
    })
    assert history_location_response.status_code == 201
    history_location = history_location_response.json()

    ingredient = client.post("/api/ingredients", json={
        "name": f"History Ingredient {suffix}", "shopping_category_id": None,
        "preferred_unit_id": each["id"], "default_location_id": pantry["id"],
        "perishable": False, "notes": None, "aliases": [],
    }).json()
    lot = client.post("/api/inventory", json={
        "ingredient_id": ingredient["id"], "location_id": pantry["id"], "quantity": "10",
        "unit_id": each["id"], "purchase_date": "2026-09-01", "opened_date": None,
        "expiration_date": None, "frozen_date": None, "thawed_date": None,
        "notes": "History source lot", "transaction_type": "PURCHASE",
    }).json()
    recipe = client.post("/api/recipes", json={
        "name": f"History Recipe {suffix}", "description": None, "base_servings": "4",
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
    output = client.post(f"/api/recipes/{recipe['id']}/outputs", json={
        "name": f"History Sauce {suffix}", "quantity": "2", "unit_id": ounce["id"],
        "notes": "History output", "active": True, "sort_order": 0,
    }).json()
    meal_name = f"History Meal {suffix}"
    meal_payload = {
        "name": meal_name, "description": "History snapshot source", "favorite": False,
        "meal_types": ["DINNER"], "tag_ids": [],
        "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
    }
    meal = client.post("/api/meals", json=meal_payload).json()
    cycle = client.post("/api/meal-cycles", json={
        "name": f"History Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-06", "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
    }).json()
    slot = cycle["slots"][0]
    planned = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]}).json()
    client.post(f"/api/planned-meals/{planned['id']}/completion")
    finalized = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["shortages"] == []

    preview = client.get(f"/api/planned-meals/{planned['id']}/completion/production-preview?actual_servings_produced=5").json()
    committed = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
        "actual_servings_produced": "5", "actual_servings_eaten": "4",
        "leftover_location_id": history_location["id"], "leftover_expiration_date": "2026-09-10",
        "leftover_notes": "History leftover",
        "outputs": [{
            "recipe_output_id": output["id"], "component_key": preview["outputs"][0]["component_key"],
            "actual_quantity": "2.5", "location_id": history_location["id"],
            "expiration_date": "2026-09-09", "notes": "History measured output",
        }],
    })
    assert committed.status_code == 200

    return {
        "meal": meal,
        "meal_payload": meal_payload,
        "meal_name": meal_name,
        "planned": planned,
        "completion": committed.json()["completion"],
        "leftover": committed.json()["leftover"],
        "output": committed.json()["outputs"][0],
        "ingredient": ingredient,
        "source_lot": lot,
        "pantry": pantry,
        "history_location": history_location,
    }


def test_meal_history_uses_immutable_completion_snapshot_and_production_provenance() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        data = _create_completed_meal(client, suffix)
        renamed = {**data["meal_payload"], "name": f"Renamed Meal {suffix}", "active": True}
        response = client.put(f"/api/meals/{data['meal']['id']}", json=renamed)
        assert response.status_code == 200

        history = client.get("/api/history/meals")
        assert history.status_code == 200
        row = next(item for item in history.json() if item["completion_id"] == data["completion"]["id"])
        assert row["meal_name"] == data["meal_name"]
        assert row["finalized_at"] is not None
        assert row["production_committed_at"] is not None
        assert Decimal(row["actual_servings_produced"]) == Decimal("5")
        assert Decimal(row["actual_servings_eaten"]) == Decimal("4")
        assert row["usages"][0]["recipe_name"].startswith("History Recipe ")
        assert row["usages"][0]["actual_ingredient_name"] == data["ingredient"]["name"]
        assert row["usages"][0]["allocations"][0]["lot_id"] == data["source_lot"]["id"]
        assert row["leftover"]["inventory_lot_id"] == data["leftover"]["inventory_lot_id"]
        assert Decimal(row["leftover"]["leftover_servings"]) == Decimal("1")
        assert row["outputs"][0]["inventory_lot_id"] == data["output"]["inventory_lot_id"]
        assert Decimal(row["outputs"][0]["actual_quantity"]) == Decimal("2.5")


def test_inventory_history_filters_and_location_provenance() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        data = _create_completed_meal(client, suffix)
        transfer = client.post(f"/api/inventory/{data['source_lot']['id']}/transfer", json={
            "to_location_id": data["history_location"]["id"], "note": "History transfer",
        })
        assert transfer.status_code == 200

        history = client.get("/api/history/inventory", params={
            "ingredient_id": data["ingredient"]["id"],
            "lot_id": data["source_lot"]["id"],
            "transaction_type": "TRANSFER",
        })
        assert history.status_code == 200
        rows = history.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["transaction_type"] == "TRANSFER"
        assert row["ingredient_name"] == data["ingredient"]["name"]
        assert row["source_type"] == "INGREDIENT"
        assert row["from_location_name"] == data["pantry"]["name"]
        assert row["to_location_name"] == data["history_location"]["name"]
        assert row["note"] == "History transfer"

        empty = client.get("/api/history/inventory", params={"lot_id": 99999999})
        assert empty.status_code == 200
        assert empty.json() == []
