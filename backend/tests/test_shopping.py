from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_shopping_item(client: TestClient, suffix: str) -> tuple[int, dict, dict, dict]:
    units = {item["code"]: item for item in client.get("/api/reference/units").json()}
    categories = {item["name"]: item for item in client.get("/api/reference/shopping-categories").json()}
    locations = {item["name"]: item for item in client.get("/api/reference/inventory-locations").json()}

    ingredient = client.post(
        "/api/ingredients",
        json={
            "name": f"Shopping Flour {suffix}",
            "shopping_category_id": categories["Pantry"]["id"],
            "preferred_unit_id": units["lb"]["id"],
            "default_location_id": locations["Pantry"]["id"],
            "perishable": False,
            "notes": None,
            "aliases": [],
        },
    )
    assert ingredient.status_code == 201
    ingredient_id = ingredient.json()["id"]

    recipe = client.post(
        "/api/recipes",
        json={
            "name": f"Shopping Recipe {suffix}",
            "description": None,
            "base_servings": "4",
            "serving_unit": "servings",
            "yield_quantity": None,
            "yield_unit_id": None,
            "prep_time_minutes": 0,
            "cook_time_minutes": 0,
            "notes": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": "1",
                "unit_id": units["lb"]["id"],
                "display_text": None,
                "preparation": None,
                "optional": False,
                "scaling_mode": "LINEAR",
                "required_state": "ANY",
                "sort_order": 0,
                "notes": None,
            }],
        },
    )
    assert recipe.status_code == 201

    meal = client.post(
        "/api/meals",
        json={
            "name": f"Shopping Meal {suffix}",
            "description": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "recipes": [{
                "recipe_id": recipe.json()["id"],
                "serving_multiplier": "1",
                "default_servings": "4",
                "sort_order": 0,
                "notes": None,
            }],
        },
    )
    assert meal.status_code == 201

    cycle = client.post(
        "/api/meal-cycles",
        json={
            "name": f"Shopping Cycle {suffix}",
            "duration_days": 1,
            "start_date": None,
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
        },
    )
    assert cycle.status_code == 201
    cycle_data = cycle.json()
    cycle_id = cycle_data["id"]
    slot_id = cycle_data["slots"][0]["id"]

    placed = client.post(
        f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal",
        json={"meal_id": meal.json()["id"]},
    )
    assert placed.status_code == 201
    generated = client.post(f"/api/shopping/{cycle_id}/regenerate")
    assert generated.status_code == 200
    return cycle_id, generated.json()["items"][0], units, locations


def test_inventory_aware_shopping_generation_and_regeneration() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, suffix)
        ingredient_id = item["ingredient_id"]

        inventory = client.post(
            "/api/inventory",
            json={
                "ingredient_id": ingredient_id,
                "location_id": locations["Pantry"]["id"],
                "quantity": "8",
                "unit_id": units["oz"]["id"],
                "purchase_date": None,
                "opened_date": None,
                "expiration_date": None,
                "frozen_date": None,
                "thawed_date": None,
                "notes": None,
                "transaction_type": "MANUAL_ADD",
            },
        )
        assert inventory.status_code == 201

        generated = client.post(f"/api/shopping/{cycle_id}/regenerate")
        assert generated.status_code == 200
        item = generated.json()["items"][0]
        assert item["shopping_category_name"] == "Pantry"
        assert item["unit_code"] == "lb"
        assert Decimal(item["required_quantity"]) == Decimal("1")
        assert Decimal(item["inventory_quantity"]) == Decimal("0.5")
        assert Decimal(item["generated_quantity"]) == Decimal("0.5")
        assert Decimal(item["final_quantity"]) == Decimal("0.5")
        assert f"Shopping Meal {suffix}" in item["source_trace"]

        adjusted = client.put(
            f"/api/shopping/{cycle_id}/items/{item['id']}",
            json={"adjustment_quantity": "0.25"},
        )
        assert adjusted.status_code == 200
        assert Decimal(adjusted.json()["items"][0]["final_quantity"]) == Decimal("0.75")

        regenerated = client.post(f"/api/shopping/{cycle_id}/regenerate")
        regenerated_item = regenerated.json()["items"][0]
        assert Decimal(regenerated_item["generated_quantity"]) == Decimal("0.5")
        assert Decimal(regenerated_item["adjustment_quantity"]) == Decimal("0.25")

        increased_inventory = client.post(
            f"/api/inventory/{inventory.json()['id']}/add",
            json={"quantity": "16", "note": "Shopping test"},
        )
        assert increased_inventory.status_code == 200
        covered = client.post(f"/api/shopping/{cycle_id}/regenerate")
        covered_item = covered.json()["items"][0]
        assert Decimal(covered_item["generated_quantity"]) == Decimal("0")
        assert Decimal(covered_item["final_quantity"]) == Decimal("0.25")


def test_complete_purchase_creates_inventory_once_and_skip_creates_none() -> None:
    with TestClient(app) as client:
        cycle_id, item, units, locations = _create_shopping_item(client, uuid4().hex[:8])
        complete = client.post(
            f"/api/shopping/{cycle_id}/items/{item['id']}/complete",
            json={
                "actual_quantity": "12",
                "actual_unit_id": units["oz"]["id"],
                "storage_location_id": locations["Pantry"]["id"],
                "purchase_date": "2026-08-29",
                "expiration_date": "2026-09-29",
                "notes": "Bought on shopping trip",
            },
        )
        assert complete.status_code == 200
        completed_item = complete.json()["items"][0]
        assert completed_item["status"] == "COMPLETED"
        assert Decimal(completed_item["actual_quantity"]) == Decimal("12")
        assert completed_item["actual_unit_code"] == "oz"
        assert completed_item["inventory_lot_id"] is not None

        lot = client.get(f"/api/inventory/{completed_item['inventory_lot_id']}")
        assert lot.status_code == 200
        lot_data = lot.json()
        assert Decimal(lot_data["quantity"]) == Decimal("12")
        assert lot_data["location_id"] == locations["Pantry"]["id"]
        assert lot_data["purchase_date"] == "2026-08-29"
        assert lot_data["expiration_date"] == "2026-09-29"
        purchase_transactions = [tx for tx in lot_data["transactions"] if tx["transaction_type"] == "PURCHASE"]
        assert len(purchase_transactions) == 1
        assert Decimal(purchase_transactions[0]["quantity_delta"]) == Decimal("12")

        duplicate = client.post(
            f"/api/shopping/{cycle_id}/items/{item['id']}/complete",
            json={
                "actual_quantity": "12",
                "actual_unit_id": units["oz"]["id"],
                "storage_location_id": locations["Pantry"]["id"],
            },
        )
        assert duplicate.status_code == 409
        lots = client.get(f"/api/inventory?ingredient_id={item['ingredient_id']}&include_empty=true").json()
        assert len([lot_item for lot_item in lots if lot_item["id"] == completed_item["inventory_lot_id"]]) == 1

        regenerated = client.post(f"/api/shopping/{cycle_id}/regenerate")
        assert regenerated.status_code == 200
        regenerated_item = next(value for value in regenerated.json()["items"] if value["id"] == item["id"])
        assert regenerated_item["status"] == "COMPLETED"
        assert regenerated_item["inventory_lot_id"] == completed_item["inventory_lot_id"]

        skip_cycle_id, skip_item, _, _ = _create_shopping_item(client, uuid4().hex[:8])
        before = client.get(f"/api/inventory?ingredient_id={skip_item['ingredient_id']}&include_empty=true").json()
        skipped = client.post(f"/api/shopping/{skip_cycle_id}/items/{skip_item['id']}/skip")
        assert skipped.status_code == 200
        skipped_item = skipped.json()["items"][0]
        assert skipped_item["status"] == "SKIPPED"
        assert skipped_item["inventory_lot_id"] is None
        after = client.get(f"/api/inventory?ingredient_id={skip_item['ingredient_id']}&include_empty=true").json()
        assert len(after) == len(before)
        repeat_skip = client.post(f"/api/shopping/{skip_cycle_id}/items/{skip_item['id']}/skip")
        assert repeat_skip.status_code == 409
