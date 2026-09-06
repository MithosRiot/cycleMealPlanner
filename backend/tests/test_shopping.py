from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_shopping_item(client: TestClient, suffix: str) -> tuple[int, dict, dict, dict]:
    units = {item["code"]: item for item in client.get("/api/reference/units").json()}
    categories = {item["name"]: item for item in client.get("/api/reference/shopping-categories").json()}
    locations = {item["name"]: item for item in client.get("/api/reference/inventory-locations").json()}
    ingredient = client.post("/api/ingredients", json={"name": f"Shopping Flour {suffix}", "shopping_category_id": categories["Pantry"]["id"], "preferred_unit_id": units["lb"]["id"], "default_location_id": locations["Pantry"]["id"], "perishable": False, "notes": None, "aliases": []})
    assert ingredient.status_code == 201
    recipe = client.post("/api/recipes", json={"name": f"Shopping Recipe {suffix}", "description": None, "base_servings": "4", "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": 0, "cook_time_minutes": 0, "notes": None, "favorite": False, "meal_types": ["DINNER"], "tag_ids": [], "ingredients": [{"ingredient_id": ingredient.json()["id"], "quantity": "1", "unit_id": units["lb"]["id"], "display_text": None, "preparation": None, "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None}]})
    assert recipe.status_code == 201
    meal = client.post("/api/meals", json={"name": f"Shopping Meal {suffix}", "description": None, "favorite": False, "meal_types": ["DINNER"], "tag_ids": [], "recipes": [{"recipe_id": recipe.json()["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}]})
    assert meal.status_code == 201
    cycle = client.post("/api/meal-cycles", json={"name": f"Shopping Cycle {suffix}", "duration_days": 1, "start_date": None, "notes": None, "slot_definitions": [{"label": "Dinner", "sort_order": 0}]})
    assert cycle.status_code == 201
    cycle_id = cycle.json()["id"]; slot_id = cycle.json()["slots"][0]["id"]
    assert client.post(f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal", json={"meal_id": meal.json()["id"]}).status_code == 201
    generated = client.post(f"/api/shopping/{cycle_id}/regenerate"); assert generated.status_code == 200
    return cycle_id, generated.json()["items"][0], units, locations


def test_inventory_aware_shopping_generation_and_regeneration() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, suffix); ingredient_id = item["ingredient_id"]
        inventory = client.post("/api/inventory", json={"ingredient_id": ingredient_id, "location_id": locations["Pantry"]["id"], "quantity": "8", "unit_id": units["oz"]["id"], "purchase_date": None, "opened_date": None, "expiration_date": None, "frozen_date": None, "thawed_date": None, "notes": None, "transaction_type": "MANUAL_ADD"})
        assert inventory.status_code == 201
        item = client.post(f"/api/shopping/{cycle_id}/regenerate").json()["items"][0]
        assert item["shopping_category_name"] == "Pantry"; assert item["unit_code"] == "lb"; assert Decimal(item["required_quantity"]) == Decimal("1"); assert Decimal(item["inventory_quantity"]) == Decimal("0.5"); assert Decimal(item["generated_quantity"]) == Decimal("0.5"); assert Decimal(item["final_quantity"]) == Decimal("0.5"); assert f"Shopping Meal {suffix}" in item["source_trace"]
        adjusted = client.put(f"/api/shopping/{cycle_id}/items/{item['id']}", json={"adjustment_quantity": "0.25"}); assert adjusted.status_code == 200; assert Decimal(adjusted.json()["items"][0]["final_quantity"]) == Decimal("0.75")
        regenerated_item = client.post(f"/api/shopping/{cycle_id}/regenerate").json()["items"][0]; assert Decimal(regenerated_item["generated_quantity"]) == Decimal("0.5"); assert Decimal(regenerated_item["adjustment_quantity"]) == Decimal("0.25")
        assert client.post(f"/api/inventory/{inventory.json()['id']}/add", json={"quantity": "16", "note": "Shopping test"}).status_code == 200
        covered_item = client.post(f"/api/shopping/{cycle_id}/regenerate").json()["items"][0]; assert Decimal(covered_item["generated_quantity"]) == Decimal("0"); assert Decimal(covered_item["final_quantity"]) == Decimal("0.25")


def test_complete_purchase_creates_inventory_once_and_skip_creates_none() -> None:
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, uuid4().hex[:8])
        payload = {"actual_quantity": "16", "actual_unit_id": units["oz"]["id"], "storage_location_id": locations["Pantry"]["id"], "purchase_date": "2026-08-29", "expiration_date": "2026-09-29", "notes": "Bought on shopping trip", "idempotency_key": f"shopping-{uuid4().hex}"}
        complete = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json=payload); assert complete.status_code == 200
        completed_item = complete.json()["items"][0]; assert completed_item["status"] == "COMPLETED"; assert Decimal(completed_item["actual_quantity"]) == Decimal("16"); assert completed_item["actual_unit_code"] == "oz"; assert completed_item["inventory_lot_id"] is not None
        lot_data = client.get(f"/api/inventory/{completed_item['inventory_lot_id']}").json(); assert Decimal(lot_data["quantity"]) == Decimal("16"); assert len([tx for tx in lot_data["transactions"] if tx["transaction_type"] == "PURCHASE"]) == 1
        duplicate = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json=payload); assert duplicate.status_code == 200; assert duplicate.json()["items"][0]["inventory_lot_id"] == completed_item["inventory_lot_id"]
        lots = client.get(f"/api/inventory?ingredient_id={item['ingredient_id']}&include_empty=true").json(); assert len([lot for lot in lots if lot["id"] == completed_item["inventory_lot_id"]]) == 1
        skip_cycle_id, skip_item, _, _ = _create_shopping_item(client, uuid4().hex[:8]); before = client.get(f"/api/inventory?ingredient_id={skip_item['ingredient_id']}&include_empty=true").json(); skipped = client.post(f"/api/shopping/{skip_cycle_id}/items/{skip_item['id']}/skip"); assert skipped.status_code == 200; assert skipped.json()["items"][0]["status"] == "SKIPPED"; after = client.get(f"/api/inventory?ingredient_id={skip_item['ingredient_id']}&include_empty=true").json(); assert len(after) == len(before); assert client.post(f"/api/shopping/{skip_cycle_id}/items/{skip_item['id']}/skip").status_code == 409


def test_partial_purchase_leaves_only_remaining_demand_pending() -> None:
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, uuid4().hex[:8]); key = f"partial-{uuid4().hex}"
        partial = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json={"actual_quantity": "8", "actual_unit_id": units["oz"]["id"], "storage_location_id": locations["Pantry"]["id"], "idempotency_key": key})
        assert partial.status_code == 200
        row = partial.json()["items"][0]; assert row["status"] == "PENDING"; assert Decimal(row["satisfied_quantity"]) == Decimal("0.5"); assert Decimal(row["remaining_quantity"]) == Decimal("0.5"); assert len(row["purchases"]) == 1
        retry = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json={"actual_quantity": "8", "actual_unit_id": units["oz"]["id"], "storage_location_id": locations["Pantry"]["id"], "idempotency_key": key}); assert retry.status_code == 200; assert len(retry.json()["items"][0]["purchases"]) == 1
        regenerated = client.post(f"/api/shopping/{cycle_id}/regenerate"); assert regenerated.status_code == 200
        row = regenerated.json()["items"][0]; assert row["status"] == "PENDING"; assert len(row["purchases"]) == 1


def test_standard_purchase_ignores_substitution_only_satisfaction_fields() -> None:
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, uuid4().hex[:8])
        result = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json={"actual_quantity": "8", "actual_unit_id": units["oz"]["id"], "satisfied_quantity": "1", "satisfied_unit_id": units["lb"]["id"], "storage_location_id": locations["Pantry"]["id"], "idempotency_key": f"stale-{uuid4().hex}"})
        assert result.status_code == 200
        row = result.json()["items"][0]
        assert row["status"] == "PENDING"
        assert Decimal(row["satisfied_quantity"]) == Decimal("0.5")
        assert Decimal(row["remaining_quantity"]) == Decimal("0.5")
        assert Decimal(row["purchases"][0]["satisfied_quantity"]) == Decimal("8")
        assert row["purchases"][0]["satisfied_unit_code"] == "oz"


def test_shopping_substitution_preserves_original_demand_and_intakes_target_once() -> None:
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, uuid4().hex[:8])
        substitute = client.post("/api/ingredients", json={"name": f"Substitute {uuid4().hex[:8]}", "shopping_category_id": item["shopping_category_id"], "preferred_unit_id": units["each"]["id"], "default_location_id": locations["Pantry"]["id"], "perishable": False, "notes": None, "aliases": []}); assert substitute.status_code == 201
        key = f"sub-{uuid4().hex}"
        result = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json={"actual_quantity": "2", "actual_unit_id": units["each"]["id"], "purchased_ingredient_id": substitute.json()["id"], "satisfied_quantity": "1", "satisfied_unit_id": units["lb"]["id"], "storage_location_id": locations["Pantry"]["id"], "notes": "UAT substitution", "idempotency_key": key})
        assert result.status_code == 200
        row = result.json()["items"][0]; assert row["ingredient_id"] == item["ingredient_id"]; assert row["status"] == "COMPLETED"; assert Decimal(row["remaining_quantity"]) == 0; assert row["purchases"][0]["purchase_kind"] == "SUBSTITUTION"; assert row["purchases"][0]["purchased_ingredient_id"] == substitute.json()["id"]
        target_lots = client.get(f"/api/inventory?ingredient_id={substitute.json()['id']}&include_empty=true").json(); assert len(target_lots) == 1; assert Decimal(target_lots[0]["quantity"]) == 2
        original_lots = client.get(f"/api/inventory?ingredient_id={item['ingredient_id']}&include_empty=true").json(); assert original_lots == []
        regenerated = client.post(f"/api/shopping/{cycle_id}/regenerate").json()["items"][0]; assert regenerated["status"] == "COMPLETED"; assert len(regenerated["purchases"]) == 1
