from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _cycle(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/meal-cycles",
        json={
            "name": name,
            "duration_days": 1,
            "start_date": None,
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
        },
    )
    assert response.status_code == 201
    return response.json()


def _place_requirement(client: TestClient, cycle: dict, ingredient_id: int, unit_id: int, quantity: str, suffix: str) -> None:
    recipe = client.post(
        "/api/recipes",
        json={
            "name": f"Staple Recipe {suffix}",
            "description": None,
            "base_servings": "1",
            "serving_unit": "serving",
            "yield_quantity": None,
            "yield_unit_id": None,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
            "notes": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": quantity,
                "unit_id": unit_id,
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
            "name": f"Staple Meal {suffix}",
            "description": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "recipes": [{
                "recipe_id": recipe.json()["id"],
                "serving_multiplier": "1",
                "default_servings": "1",
                "sort_order": 0,
                "notes": None,
            }],
        },
    )
    assert meal.status_code == 201
    slot_id = cycle["slots"][0]["id"]
    placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal.json()["id"]})
    assert placed.status_code == 201


def test_staple_rules_validate_and_replenish_without_double_counting_meal_requirements() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        categories = {item["name"]: item for item in client.get("/api/reference/shopping-categories").json()}
        locations = {item["name"]: item for item in client.get("/api/reference/inventory-locations").json()}

        invalid = client.post("/api/ingredients", json={
            "name": f"Invalid Staple {suffix}",
            "preferred_unit_id": units["lb"]["id"],
            "staple_enabled": True,
            "staple_minimum": "3",
            "staple_target": "2",
            "staple_unit_id": units["lb"]["id"],
        })
        assert invalid.status_code == 422

        incompatible = client.post("/api/ingredients", json={
            "name": f"Incompatible Staple {suffix}",
            "preferred_unit_id": units["lb"]["id"],
            "staple_enabled": True,
            "staple_minimum": "1",
            "staple_target": "2",
            "staple_unit_id": units["each"]["id"],
        })
        assert incompatible.status_code == 422

        ingredient = client.post("/api/ingredients", json={
            "name": f"Staple Flour {suffix}",
            "shopping_category_id": categories["Pantry"]["id"],
            "preferred_unit_id": units["lb"]["id"],
            "default_location_id": locations["Pantry"]["id"],
            "perishable": False,
            "staple_enabled": True,
            "staple_minimum": "1",
            "staple_target": "3",
            "staple_unit_id": units["lb"]["id"],
            "notes": None,
            "aliases": [],
        })
        assert ingredient.status_code == 201
        ingredient_id = ingredient.json()["id"]
        assert Decimal(ingredient.json()["staple_target"]) == Decimal("3")

        lot = client.post("/api/inventory", json={
            "ingredient_id": ingredient_id,
            "location_id": locations["Pantry"]["id"],
            "quantity": "2",
            "unit_id": units["lb"]["id"],
            "purchase_date": None,
            "opened_date": None,
            "expiration_date": None,
            "frozen_date": None,
            "thawed_date": None,
            "notes": None,
            "transaction_type": "MANUAL_ADD",
        })
        assert lot.status_code == 201

        staple_only_cycle = _cycle(client, f"Staple Only {suffix}")
        shopping = client.post(f"/api/shopping/{staple_only_cycle['id']}/regenerate")
        assert shopping.status_code == 200
        staple_item = next(item for item in shopping.json()["items"] if item["ingredient_id"] == ingredient_id)
        assert Decimal(staple_item["required_quantity"]) == Decimal("0")
        assert Decimal(staple_item["inventory_quantity"]) == Decimal("2")
        assert Decimal(staple_item["generated_quantity"]) == Decimal("0")

        meal_cycle = _cycle(client, f"Staple Meal Cycle {suffix}")
        _place_requirement(client, meal_cycle, ingredient_id, units["lb"]["id"], "2", suffix)
        combined = client.post(f"/api/shopping/{meal_cycle['id']}/regenerate")
        assert combined.status_code == 200
        item = next(value for value in combined.json()["items"] if value["ingredient_id"] == ingredient_id)
        assert Decimal(item["required_quantity"]) == Decimal("2")
        assert Decimal(item["inventory_quantity"]) == Decimal("2")
        assert Decimal(item["generated_quantity"]) == Decimal("3")
        assert "replenish toward target" in (item["warning"] or "")

        reservation_cycle = _cycle(client, f"Reservation Holder {suffix}")
        _place_requirement(client, reservation_cycle, ingredient_id, units["lb"]["id"], "1.5", f"R{suffix}")
        refreshed = client.post(f"/api/meal-cycles/{reservation_cycle['id']}/reservations/regenerate")
        assert refreshed.status_code == 200

        reserved_shopping = client.post(f"/api/shopping/{staple_only_cycle['id']}/regenerate")
        reserved_item = next(value for value in reserved_shopping.json()["items"] if value["ingredient_id"] == ingredient_id)
        assert Decimal(reserved_item["inventory_quantity"]) == Decimal("0.5")
        assert Decimal(reserved_item["generated_quantity"]) == Decimal("2.5")

        current = client.get(f"/api/ingredients/{ingredient_id}").json()
        current.update({"staple_enabled": False, "aliases": []})
        disabled = client.put(f"/api/ingredients/{ingredient_id}", json=current)
        assert disabled.status_code == 200
        disabled_shopping = client.post(f"/api/shopping/{staple_only_cycle['id']}/regenerate")
        disabled_item = next((value for value in disabled_shopping.json()["items"] if value["ingredient_id"] == ingredient_id), None)
        assert disabled_item is None
