from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_real_prep_schedule_tracks_serving_schedule_without_mutation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        recipe_response = client.post(
            "/api/recipes",
            json={
                "name": f"Prep Schedule Recipe {suffix}",
                "description": None,
                "base_servings": "4",
                "serving_unit": "servings",
                "yield_quantity": None,
                "yield_unit_id": None,
                "prep_time_minutes": 10,
                "cook_time_minutes": 20,
                "notes": None,
                "favorite": False,
                "meal_types": ["DINNER"],
                "tag_ids": [],
                "prep_groups": [{"client_key": "sauce", "name": "Sauce", "sort_order": 0}],
                "advance_prep": [
                    {
                        "title": "Marinate sauce",
                        "lead_time_minutes": 1440,
                        "duration_minutes": 30,
                        "instructions": "Mix and refrigerate.",
                        "prep_group_key": "sauce",
                        "sort_order": 0,
                    },
                    {
                        "title": "Set out ingredients",
                        "lead_time_minutes": 60,
                        "duration_minutes": None,
                        "instructions": None,
                        "prep_group_key": None,
                        "sort_order": 1,
                    },
                ],
                "ingredients": [],
            },
        )
        assert recipe_response.status_code == 201
        recipe = recipe_response.json()

        meal_response = client.post(
            "/api/meals",
            json={
                "name": f"Prep Schedule Meal {suffix}",
                "description": None,
                "favorite": False,
                "meal_types": ["DINNER"],
                "tag_ids": [],
                "recipes": [
                    {
                        "recipe_id": recipe["id"],
                        "serving_multiplier": "1",
                        "default_servings": "4",
                        "sort_order": 0,
                        "notes": None,
                    }
                ],
            },
        )
        assert meal_response.status_code == 201
        meal = meal_response.json()

        cycle_response = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Prep Schedule Cycle {suffix}",
                "duration_days": 2,
                "start_date": "2026-09-10",
                "notes": None,
                "slot_definitions": [
                    {"label": "Dinner", "sort_order": 0, "serving_time": "18:30:00"}
                ],
            },
        )
        assert cycle_response.status_code == 201
        cycle = cycle_response.json()
        slot = next(item for item in cycle["slots"] if item["day_number"] == 1)

        placed_response = client.post(
            f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal",
            json={"meal_id": meal["id"]},
        )
        assert placed_response.status_code == 200
        planned_meal_id = placed_response.json()["id"]

        schedule = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule")
        assert schedule.status_code == 200
        tasks = schedule.json()["tasks"]
        assert [item["title"] for item in tasks] == ["Marinate sauce", "Set out ingredients"]
        assert tasks[0]["meal_name"] == meal["name"]
        assert tasks[0]["recipe_name"] == recipe["name"]
        assert tasks[0]["prep_group_name"] == "Sauce"
        assert tasks[0]["instructions"] == "Mix and refrigerate."
        assert tasks[0]["serving_datetime"] == "2026-09-10T18:30:00"
        assert tasks[0]["start_datetime"] == "2026-09-09T18:30:00"
        assert tasks[0]["end_datetime"] == "2026-09-09T19:00:00"
        assert tasks[1]["start_datetime"] == "2026-09-10T17:30:00"
        assert all(item["planned_meal_id"] == planned_meal_id for item in tasks)

        definition_id = cycle["slot_definitions"][0]["id"]
        shifted = client.put(
            f"/api/meal-cycles/{cycle['id']}/schedule",
            json={"start_date": "2026-09-11", "serving_times": {str(definition_id): "19:30:00"}},
        )
        assert shifted.status_code == 200
        same_slot = next(item for item in shifted.json()["slots"] if item["id"] == slot["id"])
        assert same_slot["planned_meal"]["id"] == planned_meal_id

        shifted_schedule = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule").json()["tasks"]
        assert shifted_schedule[0]["serving_datetime"] == "2026-09-11T19:30:00"
        assert shifted_schedule[0]["start_datetime"] == "2026-09-10T19:30:00"

        unscheduled = client.put(
            f"/api/meal-cycles/{cycle['id']}/schedule",
            json={"start_date": None, "serving_times": {str(definition_id): "19:30:00"}},
        )
        assert unscheduled.status_code == 200
        unresolved = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule").json()["tasks"]
        assert unresolved[0]["start_datetime"] is None
        assert unresolved[0]["serving_datetime"] is None
        assert unresolved[0]["unresolved_reason"] == "Cycle start date and slot serving time are required"
