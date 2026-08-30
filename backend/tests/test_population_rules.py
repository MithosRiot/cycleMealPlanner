from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_meal(client: TestClient, name: str, meal_type: str) -> int:
    unit = next(item for item in client.get("/api/reference/units").json() if item["code"] == "each")
    ingredient = client.post(
        "/api/ingredients",
        json={
            "name": f"{name} Ingredient",
            "shopping_category_id": None,
            "preferred_unit_id": unit["id"],
            "default_location_id": None,
            "perishable": False,
            "notes": None,
            "aliases": [],
        },
    )
    recipe = client.post(
        "/api/recipes",
        json={
            "name": f"{name} Recipe",
            "description": None,
            "base_servings": "4",
            "serving_unit": "servings",
            "yield_quantity": None,
            "yield_unit_id": None,
            "prep_time_minutes": 0,
            "cook_time_minutes": 0,
            "notes": None,
            "favorite": False,
            "meal_types": [meal_type],
            "tag_ids": [],
            "ingredients": [{
                "ingredient_id": ingredient.json()["id"],
                "quantity": "1",
                "unit_id": unit["id"],
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
    meal = client.post(
        "/api/meals",
        json={
            "name": name,
            "description": None,
            "favorite": False,
            "meal_types": [meal_type],
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
    return meal.json()["id"]


def test_population_rules_constrain_random_fill_and_persist() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        breakfast_a = _create_meal(client, f"Pool Breakfast A {suffix}", "BREAKFAST")
        breakfast_b = _create_meal(client, f"Pool Breakfast B {suffix}", "BREAKFAST")
        dinner_a = _create_meal(client, f"Pool Dinner A {suffix}", "DINNER")
        dinner_b = _create_meal(client, f"Pool Dinner B {suffix}", "DINNER")

        cycle = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Pool Cycle {suffix}",
                "duration_days": 2,
                "start_date": None,
                "notes": None,
                "slot_definitions": [
                    {"label": "Breakfast", "sort_order": 0},
                    {"label": "Dinner", "sort_order": 1},
                ],
            },
        ).json()
        cycle_id = cycle["id"]

        rules_response = client.put(
            f"/api/meal-cycles/{cycle_id}/population-rules",
            json={
                "include_meal_ids": [breakfast_a, breakfast_b, dinner_a, dinner_b],
                "exclude_meal_ids": [breakfast_b],
                "slot_rules": {
                    "Dinner": {
                        "include_meal_ids": [dinner_b],
                        "exclude_meal_ids": [],
                    }
                },
            },
        )
        assert rules_response.status_code == 200
        assert '"breakfast"' not in rules_response.json()["population_rules"]
        assert '"dinner"' in rules_response.json()["population_rules"]

        filled = client.post(f"/api/meal-cycles/{cycle_id}/random-fill")
        assert filled.status_code == 200
        assert filled.json()["filled_count"] == 4

        populated = client.get(f"/api/meal-cycles/{cycle_id}").json()
        for slot in populated["slots"]:
            planned = slot["planned_meal"]
            assert planned is not None
            if slot["sort_order"] == 0:
                assert planned["meal_id"] == breakfast_a
            else:
                assert planned["meal_id"] == dinner_b

        persisted = client.get(f"/api/meal-cycles/{cycle_id}").json()["population_rules"]
        assert persisted == rules_response.json()["population_rules"]

        invalid = client.put(
            f"/api/meal-cycles/{cycle_id}/population-rules",
            json={
                "include_meal_ids": [breakfast_a],
                "exclude_meal_ids": [breakfast_a],
                "slot_rules": {},
            },
        )
        assert invalid.status_code == 422


def test_cycle_without_population_rules_keeps_legacy_random_fill() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        breakfast = _create_meal(client, f"Legacy Breakfast {suffix}", "BREAKFAST")
        cycle = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Legacy Pool Cycle {suffix}",
                "duration_days": 1,
                "start_date": None,
                "notes": None,
                "slot_definitions": [{"label": "Breakfast", "sort_order": 0}],
            },
        ).json()

        result = client.post(f"/api/meal-cycles/{cycle['id']}/random-fill")
        assert result.status_code == 200
        assert result.json()["filled_count"] == 1
        populated = client.get(f"/api/meal-cycles/{cycle['id']}").json()
        assert populated["slots"][0]["planned_meal"]["meal_id"] == breakfast
