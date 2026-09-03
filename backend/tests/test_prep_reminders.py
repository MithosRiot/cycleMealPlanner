from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.prep_schedule import _reminder_status
from app.main import app


def _recipe_payload(name: str) -> dict:
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
        "advance_prep": [{
            "task_type": "THAW",
            "title": "Thaw protein",
            "lead_time_minutes": 120,
            "duration_minutes": 10,
            "instructions": "Move to refrigerator.",
            "reminder_enabled": True,
            "reminder_offset_minutes": 30,
            "prep_group_key": None,
            "sort_order": 0,
        }],
        "equipment": [],
        "ingredients": [],
    }


def test_reminder_status_boundaries() -> None:
    now = datetime(2026, 9, 3, 12, 0)
    assert _reminder_status(False, None, None, now) == "DISABLED"
    assert _reminder_status(True, None, None, now) == "UNSCHEDULED"
    assert _reminder_status(True, now + timedelta(minutes=10), now + timedelta(minutes=30), now) == "UPCOMING"
    assert _reminder_status(True, now - timedelta(minutes=1), now + timedelta(minutes=30), now) == "DUE"
    assert _reminder_status(True, now - timedelta(minutes=31), now - timedelta(minutes=1), now) == "OVERDUE"


def test_reminder_settings_schedule_and_legacy_edit_preservation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        created = client.post("/api/recipes", json=_recipe_payload(f"Reminder Recipe {suffix}"))
        assert created.status_code == 201
        recipe = created.json()
        prep = recipe["advance_prep"][0]
        assert prep["reminder_enabled"] is True
        assert prep["reminder_offset_minutes"] == 30

        disabled = client.put(f"/api/recipes/{recipe['id']}/advance-prep/{prep['id']}/reminder", params={"enabled": "false"})
        assert disabled.status_code == 200
        assert disabled.json()["advance_prep"][0]["reminder_enabled"] is False
        assert disabled.json()["advance_prep"][0]["reminder_offset_minutes"] is None

        enabled = client.put(f"/api/recipes/{recipe['id']}/advance-prep/{prep['id']}/reminder", params={"enabled": "true"})
        assert enabled.status_code == 200
        assert enabled.json()["advance_prep"][0]["reminder_offset_minutes"] == 15

        custom = client.put(f"/api/recipes/{recipe['id']}/advance-prep/{prep['id']}/reminder", params={"enabled": "true", "offset_minutes": 45})
        assert custom.status_code == 200
        assert custom.json()["advance_prep"][0]["reminder_offset_minutes"] == 45

        invalid = client.put(f"/api/recipes/{recipe['id']}/advance-prep/{prep['id']}/reminder", params={"enabled": "true", "offset_minutes": -1})
        assert invalid.status_code == 422

        legacy_payload = _recipe_payload(recipe["name"])
        legacy_payload["active"] = True
        legacy_payload["advance_prep"][0].pop("reminder_enabled")
        legacy_payload["advance_prep"][0].pop("reminder_offset_minutes")
        legacy_payload["advance_prep"][0]["instructions"] = "Edited without reminder fields."
        saved = client.put(f"/api/recipes/{recipe['id']}", json=legacy_payload)
        assert saved.status_code == 200
        assert saved.json()["advance_prep"][0]["reminder_enabled"] is True
        assert saved.json()["advance_prep"][0]["reminder_offset_minutes"] == 45

        meal = client.post("/api/meals", json={
            "name": f"Reminder Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        future_date = date.today() + timedelta(days=2)
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Reminder Cycle {suffix}", "duration_days": 1,
            "start_date": future_date.isoformat(), "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot = cycle["slots"][0]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]})
        assert placed.status_code in (200, 201)

        schedule = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule")
        assert schedule.status_code == 200
        task = schedule.json()["tasks"][0]
        assert task["reminder_enabled"] is True
        assert task["reminder_offset_minutes"] == 45
        assert task["start_datetime"].endswith("T16:00:00")
        assert task["reminder_at"].endswith("T15:15:00")
        assert task["reminder_status"] == "UPCOMING"

        definition_id = cycle["slot_definitions"][0]["id"]
        shifted = client.put(f"/api/meal-cycles/{cycle['id']}/schedule", json={
            "start_date": future_date.isoformat(),
            "serving_times": {str(definition_id): "19:00:00"},
        })
        assert shifted.status_code == 200
        shifted_task = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule").json()["tasks"][0]
        assert shifted_task["start_datetime"].endswith("T17:00:00")
        assert shifted_task["reminder_at"].endswith("T16:15:00")

        unscheduled = client.put(f"/api/meal-cycles/{cycle['id']}/schedule", json={
            "start_date": None,
            "serving_times": {str(definition_id): "19:00:00"},
        })
        assert unscheduled.status_code == 200
        unresolved = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule").json()["tasks"][0]
        assert unresolved["reminder_at"] is None
        assert unresolved["reminder_status"] == "UNSCHEDULED"
