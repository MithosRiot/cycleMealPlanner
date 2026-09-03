from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


TASK_TYPES = ["PREP", "THAW", "MARINATE", "SOAK", "PROOF"]


def _recipe_payload(name: str, task_types: list[str]) -> dict:
    return {
        "name": name,
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
        "prep_groups": [],
        "advance_prep": [
            {
                "task_type": task_type,
                "title": f"{task_type} task",
                "lead_time_minutes": (index + 1) * 60,
                "duration_minutes": 10,
                "instructions": f"Do {task_type.lower()} work.",
                "prep_group_key": None,
                "sort_order": index,
            }
            for index, task_type in enumerate(task_types)
        ],
        "equipment": [],
        "ingredients": [],
    }


def test_recipe_round_trips_all_typed_prep_tasks_and_rejects_invalid_type() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        created = client.post("/api/recipes", json=_recipe_payload(f"Typed Prep {suffix}", TASK_TYPES))
        assert created.status_code == 201
        recipe = created.json()
        assert [item["task_type"] for item in recipe["advance_prep"]] == TASK_TYPES

        invalid = _recipe_payload(f"Invalid Typed Prep {suffix}", ["PREP"])
        invalid["advance_prep"][0]["task_type"] = "FERMENT"
        response = client.post("/api/recipes", json=invalid)
        assert response.status_code == 422


def test_type_endpoint_and_legacy_recipe_edit_preserve_task_type() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        created = client.post("/api/recipes", json=_recipe_payload(f"Typed Preserve {suffix}", ["PREP"]))
        assert created.status_code == 201
        recipe = created.json()
        prep = recipe["advance_prep"][0]

        typed = client.put(f"/api/recipes/{recipe['id']}/advance-prep/{prep['id']}/type", params={"task_type": "THAW"})
        assert typed.status_code == 200
        assert typed.json()["advance_prep"][0]["task_type"] == "THAW"

        invalid = client.put(f"/api/recipes/{recipe['id']}/advance-prep/{prep['id']}/type", params={"task_type": "FERMENT"})
        assert invalid.status_code == 422

        # Simulate the pre-task-type Recipe editor payload: task_type omitted.
        legacy_payload = _recipe_payload(recipe["name"], ["PREP"])
        legacy_payload["active"] = True
        legacy_payload["advance_prep"][0].pop("task_type")
        legacy_payload["advance_prep"][0]["instructions"] = "Updated by legacy editor payload."
        saved = client.put(f"/api/recipes/{recipe['id']}", json=legacy_payload)
        assert saved.status_code == 200
        assert saved.json()["advance_prep"][0]["task_type"] == "THAW"
        assert saved.json()["advance_prep"][0]["instructions"] == "Updated by legacy editor payload."


def test_typed_prep_flows_through_real_schedule_without_inventory_mutation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        recipe = client.post("/api/recipes", json=_recipe_payload(f"Typed Schedule Recipe {suffix}", ["MARINATE", "PROOF"])).json()
        meal = client.post(
            "/api/meals",
            json={
                "name": f"Typed Schedule Meal {suffix}",
                "description": None,
                "favorite": False,
                "meal_types": ["DINNER"],
                "tag_ids": [],
                "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
            },
        ).json()
        cycle = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Typed Schedule Cycle {suffix}",
                "duration_days": 1,
                "start_date": "2026-09-20",
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
            },
        ).json()
        slot = cycle["slots"][0]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]})
        assert placed.status_code in (200, 201)

        before_inventory = client.get("/api/inventory?include_empty=true").json()
        schedule = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule")
        assert schedule.status_code == 200
        tasks = schedule.json()["tasks"]
        assert [item["task_type"] for item in tasks] == ["PROOF", "MARINATE"]
        assert tasks[0]["start_datetime"] == "2026-09-20T16:00:00"
        assert tasks[1]["start_datetime"] == "2026-09-20T17:00:00"
        after_inventory = client.get("/api/inventory?include_empty=true").json()
        assert after_inventory == before_inventory
