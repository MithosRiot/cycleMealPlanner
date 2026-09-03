from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_cooking_steps_and_planned_meal_mode_follow_current_servings() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        unit = next(item for item in units if item["code"] == "each")
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Cooking Onion {suffix}", "shopping_category_id": None,
            "preferred_unit_id": unit["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        recipe = client.post("/api/recipes", json={
            "name": f"Cooking Recipe {suffix}", "description": None, "base_servings": "4",
            "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
            "prep_time_minutes": 5, "cook_time_minutes": 10, "notes": None, "favorite": False,
            "meal_types": ["COOK_TEST"], "tag_ids": [],
            "prep_groups": [{"client_key": "main", "name": "Main prep", "sort_order": 0}],
            "advance_prep": [], "equipment": [],
            "ingredients": [{"ingredient_id": ingredient["id"], "prep_group_key": "main", "quantity": "2", "unit_id": unit["id"], "display_text": None, "preparation": "diced", "prep_method": "CHOP", "prep_size": "small", "prep_state": "fresh", "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None, "substitutions": []}],
        }).json()
        group_id = recipe["prep_groups"][0]["id"]
        saved = client.put(f"/api/recipes/{recipe['id']}/cooking-steps", json=[
            {"title": "Cook onions", "instructions": "Cook until soft.", "prep_group_id": group_id, "sort_order": 0},
            {"title": "Finish", "instructions": "Taste and serve.", "prep_group_id": None, "sort_order": 1},
        ])
        assert saved.status_code == 200
        assert [row["title"] for row in saved.json()] == ["Cook onions", "Finish"]

        meal = client.post("/api/meals", json={
            "name": f"Cooking Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["COOK_TEST"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Cooking Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Cook Test", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]})
        assert placed.status_code == 201

        mode = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode")
        assert mode.status_code == 200
        cooking_meal = mode.json()["meals"][0]
        assert [step["title"] for step in cooking_meal["steps"]] == ["Cook onions", "Finish"]
        assert cooking_meal["steps"][0]["step_number"] == 1
        assert cooking_meal["steps"][1]["step_number"] == 2
        assert Decimal(cooking_meal["steps"][0]["ingredients"][0]["quantity"]) == Decimal("2")

        updated = client.put(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal/planning", json={
            "planned_servings": "8", "planned_leftover_servings": "0", "component_serving_overrides": {},
        })
        assert updated.status_code == 200
        changed = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode").json()["meals"][0]
        assert Decimal(changed["steps"][0]["ingredients"][0]["quantity"]) == Decimal("4")

        reordered = client.put(f"/api/recipes/{recipe['id']}/cooking-steps", json=[
            {"title": "Finish first", "instructions": None, "prep_group_id": None, "sort_order": 0},
        ])
        assert reordered.status_code == 200
        refreshed = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode").json()["meals"][0]
        assert [step["title"] for step in refreshed["steps"]] == ["Finish first"]
