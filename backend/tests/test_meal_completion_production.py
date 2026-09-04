from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _setup_completed_meal(client: TestClient, suffix: str) -> tuple[dict, dict, dict, dict, int]:
    units = {item["code"]: item for item in client.get("/api/reference/units").json()}
    each = units["each"]
    ounce = units["oz"]
    refrigerator = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Refrigerator")
    pantry = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Pantry")

    ingredient = client.post("/api/ingredients", json={
        "name": f"Production Ingredient {suffix}", "shopping_category_id": None,
        "preferred_unit_id": each["id"], "default_location_id": pantry["id"],
        "perishable": False, "notes": None, "aliases": [],
    }).json()
    lot = client.post("/api/inventory", json={
        "ingredient_id": ingredient["id"], "location_id": pantry["id"], "quantity": "10",
        "unit_id": each["id"], "purchase_date": "2026-09-01", "opened_date": None,
        "expiration_date": None, "frozen_date": None, "thawed_date": None, "notes": None,
        "transaction_type": "MANUAL_ADD",
    }).json()
    recipe = client.post("/api/recipes", json={
        "name": f"Production Recipe {suffix}", "description": None, "base_servings": "4",
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
        "name": f"Prepared Sauce {suffix}", "quantity": "2", "unit_id": ounce["id"],
        "notes": "Reusable output", "active": True, "sort_order": 0,
    }).json()
    meal = client.post("/api/meals", json={
        "name": f"Production Meal {suffix}", "description": None, "favorite": False,
        "meal_types": ["DINNER"], "tag_ids": [],
        "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
    }).json()
    cycle = client.post("/api/meal-cycles", json={
        "name": f"Production Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
    }).json()
    slot = cycle["slots"][0]
    planned = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]}).json()
    draft = client.post(f"/api/planned-meals/{planned['id']}/completion").json()
    assert draft["status"] == "DRAFT"
    finalized = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["completion"]["status"] == "FINALIZED"
    return planned, recipe, output, lot, refrigerator["id"]


def test_production_records_partial_leftover_output_provenance_and_is_idempotent() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        planned, recipe, output, ingredient_lot, refrigerator_id = _setup_completed_meal(client, suffix)
        before_lot = client.get(f"/api/inventory/{ingredient_lot['id']}").json()
        consume_count = sum(1 for tx in before_lot["transactions"] if tx["transaction_type"] == "CONSUME")
        assert consume_count == 1

        preview = client.get(f"/api/planned-meals/{planned['id']}/completion/production-preview?actual_servings_produced=6")
        assert preview.status_code == 200
        preview_body = preview.json()
        assert Decimal(preview_body["planned_servings"]) == Decimal("4")
        assert Decimal(preview_body["default_actual_servings_produced"]) == Decimal("6")
        assert Decimal(preview_body["default_actual_servings_eaten"]) == Decimal("4")
        assert Decimal(preview_body["default_leftover_servings"]) == Decimal("2")
        output_preview = preview_body["outputs"][0]
        assert output_preview["recipe_output_id"] == output["id"]
        assert Decimal(output_preview["base_quantity"]) == Decimal("2")
        assert Decimal(output_preview["calculated_quantity"]) == Decimal("3")

        committed = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
            "actual_servings_produced": "6", "actual_servings_eaten": "4",
            "leftover_location_id": refrigerator_id, "leftover_expiration_date": "2026-09-08",
            "leftover_notes": "two dinner servings",
            "outputs": [{
                "recipe_output_id": output["id"], "component_key": output_preview["component_key"],
                "actual_quantity": "2.5", "location_id": refrigerator_id,
                "expiration_date": "2026-09-07", "notes": "measured after cooking",
            }],
        })
        assert committed.status_code == 200
        body = committed.json()
        assert body["completion"]["production_committed_at"] is not None
        assert Decimal(body["completion"]["snapshot_planned_servings"]) == Decimal("4")
        leftover = body["leftover"]
        assert leftover["status"] == "AVAILABLE"
        assert Decimal(leftover["leftover_servings"]) == Decimal("2")
        assert leftover["location_id"] == refrigerator_id
        assert leftover["expiration_date"] == "2026-09-08"
        assert leftover["inventory_lot_id"] is not None
        assert leftover["inventory_transaction_id"] is not None

        leftover_lot = client.get(f"/api/inventory/{leftover['inventory_lot_id']}").json()
        assert leftover_lot["source_type"] == "LEFTOVER"
        assert leftover_lot["source_id"] == leftover["id"]
        assert Decimal(leftover_lot["quantity"]) == Decimal("2")
        assert leftover_lot["transactions"][-1]["transaction_type"] == "PRODUCTION"

        produced_output = body["outputs"][0]
        assert produced_output["recipe_output_id"] == output["id"]
        assert Decimal(produced_output["calculated_quantity"]) == Decimal("3")
        assert Decimal(produced_output["actual_quantity"]) == Decimal("2.5")
        assert produced_output["quantity_overridden"] is True
        output_lot = client.get(f"/api/inventory/{produced_output['inventory_lot_id']}").json()
        assert output_lot["source_type"] == "RECIPE_OUTPUT"
        assert output_lot["source_id"] == produced_output["id"]
        assert Decimal(output_lot["quantity"]) == Decimal("2.5")
        assert output_lot["transactions"][-1]["transaction_type"] == "PRODUCTION"

        ingredient_after = client.get(f"/api/inventory/{ingredient_lot['id']}").json()
        assert sum(1 for tx in ingredient_after["transactions"] if tx["transaction_type"] == "CONSUME") == consume_count
        assert ingredient_after["quantity"] == before_lot["quantity"]

        repeated = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
            "actual_servings_produced": "99", "actual_servings_eaten": "0", "leftover_location_id": refrigerator_id,
            "leftover_expiration_date": None, "leftover_notes": None,
            "outputs": [{"recipe_output_id": output["id"], "component_key": output_preview["component_key"], "actual_quantity": "99", "location_id": refrigerator_id, "expiration_date": None, "notes": None}],
        })
        assert repeated.status_code == 200
        repeated_body = repeated.json()
        assert repeated_body["leftover"]["id"] == leftover["id"]
        assert repeated_body["outputs"][0]["id"] == produced_output["id"]
        assert Decimal(repeated_body["leftover"]["leftover_servings"]) == Decimal("2")
        assert Decimal(repeated_body["outputs"][0]["actual_quantity"]) == Decimal("2.5")

        update_output = client.put(f"/api/recipes/{recipe['id']}/outputs/{output['id']}", json={
            "name": output["name"], "quantity": "9", "unit_id": output["unit_id"], "notes": "changed later", "active": True, "sort_order": 0,
        })
        assert update_output.status_code == 200
        history = client.get(f"/api/planned-meals/{planned['id']}/completion/production").json()
        assert Decimal(history["outputs"][0]["base_quantity"]) == Decimal("2")
        assert Decimal(history["outputs"][0]["calculated_quantity"]) == Decimal("3")
        assert Decimal(history["outputs"][0]["actual_quantity"]) == Decimal("2.5")


def test_production_zero_leftover_and_validation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        planned, _recipe, output, _ingredient_lot, refrigerator_id = _setup_completed_meal(client, suffix)
        preview = client.get(f"/api/planned-meals/{planned['id']}/completion/production-preview").json()
        output_preview = preview["outputs"][0]

        invalid = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
            "actual_servings_produced": "4", "actual_servings_eaten": "5", "leftover_location_id": None,
            "leftover_expiration_date": None, "leftover_notes": None,
            "outputs": [{"recipe_output_id": output["id"], "component_key": output_preview["component_key"], "actual_quantity": "0", "location_id": None, "expiration_date": None, "notes": None}],
        })
        assert invalid.status_code == 422

        negative = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
            "actual_servings_produced": "-1", "actual_servings_eaten": "0", "outputs": [],
        })
        assert negative.status_code == 422

        committed = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
            "actual_servings_produced": "4", "actual_servings_eaten": "4", "leftover_location_id": None,
            "leftover_expiration_date": None, "leftover_notes": None,
            "outputs": [{"recipe_output_id": output["id"], "component_key": output_preview["component_key"], "actual_quantity": "0", "location_id": None, "expiration_date": None, "notes": None}],
        })
        assert committed.status_code == 200
        body = committed.json()
        assert body["leftover"]["status"] == "NONE"
        assert Decimal(body["leftover"]["leftover_servings"]) == 0
        assert body["leftover"]["inventory_lot_id"] is None
        assert body["leftover"]["inventory_transaction_id"] is None
        assert body["outputs"][0]["inventory_lot_id"] is None
