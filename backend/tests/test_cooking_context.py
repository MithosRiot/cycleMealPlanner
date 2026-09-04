from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_cooking_mode_exposes_step_equipment_and_temperatures() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        unit = next(item for item in units if item["code"] == "each")
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Context Ingredient {suffix}", "shopping_category_id": None,
            "preferred_unit_id": unit["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        skillet = client.post("/api/equipment", json={
            "name": f"Context Skillet {suffix}", "category": "COOKWARE", "notes": None,
        }).json()
        recipe = client.post("/api/recipes", json={
            "name": f"Context Recipe {suffix}", "description": None, "base_servings": "4",
            "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
            "prep_time_minutes": 5, "cook_time_minutes": 10, "notes": None, "favorite": False,
            "meal_types": ["CONTEXT_TEST"], "tag_ids": [], "prep_groups": [], "advance_prep": [],
            "equipment": [{"equipment_id": skillet["id"], "quantity": 1, "notes": "Use a heavy pan", "sort_order": 0}],
            "ingredients": [{"ingredient_id": ingredient["id"], "prep_group_key": None, "quantity": "1", "unit_id": unit["id"], "display_text": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None, "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None, "substitutions": []}],
        }).json()
        recipe_equipment_id = recipe["equipment"][0]["id"]
        saved = client.put(f"/api/recipes/{recipe['id']}/cooking-steps", json=[{
            "title": "Sear", "instructions": "Sear until browned.", "prep_group_id": None, "sort_order": 0,
            "timers": [], "recipe_equipment_ids": [recipe_equipment_id],
            "temperatures": [
                {"label": "Pan", "value": "400", "unit": "F", "notes": "Preheat well", "sort_order": 0},
                {"label": "Internal", "value": "74", "unit": "C", "notes": None, "sort_order": 1},
            ],
        }])
        assert saved.status_code == 200
        step = saved.json()[0]
        assert step["equipment"][0]["equipment_name"] == skillet["name"]
        assert step["equipment"][0]["quantity"] == 1
        assert step["equipment"][0]["notes"] == "Use a heavy pan"
        assert [(row["label"], row["unit"]) for row in step["temperatures"]] == [("Pan", "F"), ("Internal", "C")]

        meal = client.post("/api/meals", json={
            "name": f"Context Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["CONTEXT_TEST"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Context Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-06", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        assert client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]}).status_code == 201

        cooking_step = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode").json()["meals"][0]["steps"][0]
        assert cooking_step["equipment"][0]["equipment_name"] == skillet["name"]
        assert cooking_step["equipment"][0]["quantity"] == 1
        assert [(row["label"], row["unit"]) for row in cooking_step["temperatures"]] == [("Pan", "F"), ("Internal", "C")]


def test_step_rejects_equipment_requirement_from_another_recipe() -> None:
    with TestClient(app) as client:
        recipes = client.get("/api/recipes").json()
        recipes_with_equipment = [recipe for recipe in recipes if recipe["equipment"]]
        assert len(recipes_with_equipment) >= 2
        first = recipes_with_equipment[0]
        second = recipes_with_equipment[1]
        response = client.put(f"/api/recipes/{first['id']}/cooking-steps", json=[{
            "title": "Invalid equipment", "instructions": None, "prep_group_id": None, "sort_order": 0,
            "timers": [], "recipe_equipment_ids": [second["equipment"][0]["id"]], "temperatures": [],
        }])
        assert response.status_code == 422
