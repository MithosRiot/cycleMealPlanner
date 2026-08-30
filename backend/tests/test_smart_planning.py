import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.planned_meals import _meal_weight
from app.main import app
from app.models.ingredient import Tag
from app.models.meal import Meal


def _create_meal(client: TestClient, name: str, meal_type: str) -> int:
    unit = next(item for item in client.get("/api/reference/units").json() if item["code"] == "each")
    ingredient = client.post(
        "/api/ingredients",
        json={"name": f"{name} Ingredient", "shopping_category_id": None, "preferred_unit_id": unit["id"], "default_location_id": None, "perishable": False, "notes": None, "aliases": []},
    )
    assert ingredient.status_code == 201
    recipe = client.post(
        "/api/recipes",
        json={
            "name": f"{name} Recipe", "description": None, "base_servings": "4", "serving_unit": "servings",
            "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": 0, "cook_time_minutes": 0,
            "notes": None, "favorite": False, "meal_types": [meal_type], "tag_ids": [],
            "ingredients": [{"ingredient_id": ingredient.json()["id"], "quantity": "1", "unit_id": unit["id"], "display_text": None, "preparation": None, "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None}],
        },
    )
    assert recipe.status_code == 201
    meal = client.post(
        "/api/meals",
        json={"name": name, "description": None, "favorite": False, "meal_types": [meal_type], "tag_ids": [], "recipes": [{"recipe_id": recipe.json()["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}]},
    )
    assert meal.status_code == 201
    return meal.json()["id"]


def test_repeat_spacing_and_preference_persistence() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        meal_a = _create_meal(client, f"Spacing A {suffix}", "BREAKFAST")
        meal_b = _create_meal(client, f"Spacing B {suffix}", "BREAKFAST")
        cycle = client.post(
            "/api/meal-cycles",
            json={"name": f"Spacing Cycle {suffix}", "duration_days": 3, "start_date": None, "notes": None, "slot_definitions": [{"label": "Breakfast", "sort_order": 0}]},
        ).json()
        cycle_id = cycle["id"]

        rules = client.put(
            f"/api/meal-cycles/{cycle_id}/population-rules",
            json={"include_meal_ids": [meal_a, meal_b], "exclude_meal_ids": [], "slot_rules": {}},
        )
        assert rules.status_code == 200

        preferences = client.put(
            f"/api/meal-cycles/{cycle_id}/smart-preferences",
            json={"repeat_spacing_days": 1, "favorite_boost": 2, "history_penalty": 0.5, "tag_weights": {}},
        )
        assert preferences.status_code == 200
        saved = json.loads(preferences.json()["smart_preferences"])
        assert saved["repeat_spacing_days"] == 1
        assert saved["favorite_boost"] == 2
        assert saved["history_penalty"] == 0.5

        filled = client.post(f"/api/meal-cycles/{cycle_id}/random-fill")
        assert filled.status_code == 200
        assert filled.json()["filled_count"] == 3
        populated = client.get(f"/api/meal-cycles/{cycle_id}").json()
        by_day = sorted(populated["slots"], key=lambda slot: slot["day_number"])
        assert by_day[0]["planned_meal"]["meal_id"] != by_day[1]["planned_meal"]["meal_id"]
        assert by_day[1]["planned_meal"]["meal_id"] != by_day[2]["planned_meal"]["meal_id"]

        persisted = json.loads(client.get(f"/api/meal-cycles/{cycle_id}").json()["smart_preferences"])
        assert persisted == saved


def test_smart_weight_favorite_tag_and_history() -> None:
    tag = Tag(id=123, household_id=1, name="Preferred", normalized_name="preferred", category="CUSTOM", active=True)
    neutral = Meal(id=1, household_id=1, name="Neutral", normalized_name="neutral", favorite=False, active=True)
    neutral.tags = []
    preferred = Meal(id=2, household_id=1, name="Preferred", normalized_name="preferred", favorite=True, active=True)
    preferred.tags = [tag]
    preferences = {"favorite_boost": 2, "tag_weights": {"123": 3}, "history_penalty": 0.5}

    neutral_weight = _meal_weight(neutral, preferences, {})
    preferred_weight = _meal_weight(preferred, preferences, {})
    penalized_weight = _meal_weight(preferred, preferences, {2: 4})

    assert preferred_weight == neutral_weight * 6
    assert 0 < penalized_weight < preferred_weight
