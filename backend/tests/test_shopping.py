from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_inventory_aware_shopping_generation_and_regeneration() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
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
        recipe_id = recipe.json()["id"]

        meal = client.post(
            "/api/meals",
            json={
                "name": f"Shopping Meal {suffix}",
                "description": None,
                "favorite": False,
                "meal_types": ["DINNER"],
                "tag_ids": [],
                "recipes": [{
                    "recipe_id": recipe_id,
                    "serving_multiplier": "1",
                    "default_servings": "4",
                    "sort_order": 0,
                    "notes": None,
                }],
            },
        )
        assert meal.status_code == 201
        meal_id = meal.json()["id"]

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
            json={"meal_id": meal_id},
        )
        assert placed.status_code == 201

        generated = client.post(f"/api/shopping/{cycle_id}/regenerate")
        assert generated.status_code == 200
        data = generated.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
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
        adjusted_item = adjusted.json()["items"][0]
        assert Decimal(adjusted_item["final_quantity"]) == Decimal("0.75")

        regenerated = client.post(f"/api/shopping/{cycle_id}/regenerate")
        assert regenerated.status_code == 200
        regenerated_item = regenerated.json()["items"][0]
        assert Decimal(regenerated_item["generated_quantity"]) == Decimal("0.5")
        assert Decimal(regenerated_item["adjustment_quantity"]) == Decimal("0.25")
        assert Decimal(regenerated_item["final_quantity"]) == Decimal("0.75")

        increased_inventory = client.post(
            f"/api/inventory/{inventory.json()['id']}/add",
            json={"quantity": "16", "note": "Shopping test"},
        )
        assert increased_inventory.status_code == 200
        covered = client.post(f"/api/shopping/{cycle_id}/regenerate")
        assert covered.status_code == 200
        covered_item = covered.json()["items"][0]
        assert Decimal(covered_item["generated_quantity"]) == Decimal("0")
        assert Decimal(covered_item["final_quantity"]) == Decimal("0.25")
