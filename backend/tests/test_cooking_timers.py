import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_multiple_cooking_timers_persist_per_planned_meal() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        unit = next(item for item in client.get("/api/reference/units").json() if item["code"] == "each")
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Timer Ingredient {suffix}", "shopping_category_id": None,
            "preferred_unit_id": unit["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        recipe = client.post("/api/recipes", json={
            "name": f"Timer Recipe {suffix}", "description": None, "base_servings": "4",
            "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
            "prep_time_minutes": 1, "cook_time_minutes": 5, "notes": None, "favorite": False,
            "meal_types": ["TIMER_TEST"], "tag_ids": [], "prep_groups": [], "advance_prep": [], "equipment": [],
            "ingredients": [{"ingredient_id": ingredient["id"], "prep_group_key": None, "quantity": "1", "unit_id": unit["id"], "display_text": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None, "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None, "substitutions": []}],
        }).json()
        steps = client.put(f"/api/recipes/{recipe['id']}/cooking-steps", json=[{
            "title": "Cook", "instructions": "Run timers.", "prep_group_id": None, "sort_order": 0,
            "timers": [
                {"label": "Short", "duration_seconds": 2, "notes": None, "sort_order": 0},
                {"label": "Long", "duration_seconds": 20, "notes": None, "sort_order": 1},
            ],
        }]).json()
        timer_ids = [timer["id"] for timer in steps[0]["timers"]]

        meal = client.post("/api/meals", json={
            "name": f"Timer Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["TIMER_TEST"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Timer Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]}).json()
        planned_meal_id = placed["id"]

        first = client.post(f"/api/planned-meals/{planned_meal_id}/cooking-timers/{timer_ids[0]}", json={"action": "START"})
        second = client.post(f"/api/planned-meals/{planned_meal_id}/cooking-timers/{timer_ids[1]}", json={"action": "START"})
        assert first.status_code == 200 and second.status_code == 200

        mode = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode").json()["meals"][0]
        timers = mode["steps"][0]["timers"]
        assert [timer["status"] for timer in timers] == ["RUNNING", "RUNNING"]
        assert all(timer["ends_at_epoch"] is not None for timer in timers)

        paused = client.post(f"/api/planned-meals/{planned_meal_id}/cooking-timers/{timer_ids[1]}", json={"action": "PAUSE"}).json()
        assert paused["status"] == "PAUSED" and 0 < paused["remaining_seconds"] <= 20
        reset = client.post(f"/api/planned-meals/{planned_meal_id}/cooking-timers/{timer_ids[1]}", json={"action": "RESET"}).json()
        assert reset["status"] == "READY" and reset["remaining_seconds"] == 20

        time.sleep(2.1)
        refreshed = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode").json()["meals"][0]
        short = next(timer for timer in refreshed["steps"][0]["timers"] if timer["timer_id"] == timer_ids[0])
        assert short["status"] == "COMPLETED" and short["remaining_seconds"] == 0

        dismissed = client.post(f"/api/planned-meals/{planned_meal_id}/cooking-timers/{timer_ids[0]}", json={"action": "DISMISS"})
        assert dismissed.status_code == 200
        after_dismiss = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode").json()["meals"][0]["steps"][0]["timers"]
        assert timer_ids[0] not in {timer["timer_id"] for timer in after_dismiss}
