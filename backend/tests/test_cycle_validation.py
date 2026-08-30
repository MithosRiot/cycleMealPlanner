from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_meal(client: TestClient, suffix: str) -> tuple[int, int]:
    unit = next(item for item in client.get("/api/reference/units").json() if item["code"] == "each")
    ingredient = client.post(
        "/api/ingredients",
        json={
            "name": f"Validation Ingredient {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": unit["id"],
            "default_location_id": None,
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
            "name": f"Validation Recipe {suffix}",
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
                "quantity": "2",
                "unit_id": unit["id"],
                "display_text": None,
                "preparation": None,
                "optional": False,
                "scaling_mode": "MANUAL",
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
            "name": f"Validation Meal {suffix}",
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
    return meal.json()["id"], ingredient_id


def test_validation_reports_empty_slots_and_no_eligible_meals() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Empty Validation {suffix}",
                "duration_days": 2,
                "start_date": None,
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
            },
        )
        assert cycle.status_code == 201
        response = client.get(f"/api/meal-cycles/{cycle.json()['id']}/validate")
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["error_count"] == 2
        codes = [item["code"] for item in body["issues"]]
        assert codes.count("EMPTY_SLOT") == 2
        assert "NO_ELIGIBLE_MEALS" in codes


def test_validation_reports_manual_scaling_shortage_and_rule_gap_without_mutation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        meal_id, ingredient_id = _create_meal(client, suffix)
        cycle = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Validation Cycle {suffix}",
                "duration_days": 1,
                "start_date": "2026-09-01",
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
            },
        ).json()
        slot_id = cycle["slots"][0]["id"]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal_id})
        assert placed.status_code == 201

        rules = client.put(
            f"/api/meal-cycles/{cycle['id']}/population-rules",
            json={"include_meal_ids": [], "exclude_meal_ids": [meal_id], "slot_rules": {}},
        )
        assert rules.status_code == 200

        before_inventory = client.get(f"/api/inventory?ingredient_id={ingredient_id}").json()
        first = client.get(f"/api/meal-cycles/{cycle['id']}/validate")
        second = client.get(f"/api/meal-cycles/{cycle['id']}/validate")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()
        body = first.json()
        codes = [item["code"] for item in body["issues"]]
        assert "MANUAL_SCALING_REVIEW" in codes
        assert "INVENTORY_SHORTAGE" in codes
        assert "NO_ELIGIBLE_MEALS" in codes
        assert body["valid"] is True
        assert client.get(f"/api/inventory?ingredient_id={ingredient_id}").json() == before_inventory
