from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_activation_requires_schedule_and_zero_blocking_validation_errors() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        unscheduled = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Lifecycle Unscheduled {suffix}",
                "duration_days": 1,
                "start_date": None,
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:30:00"}],
            },
        ).json()
        blocked_schedule = client.post(f"/api/meal-cycles/{unscheduled['id']}/activate")
        assert blocked_schedule.status_code == 409
        assert blocked_schedule.json()["detail"] == "Set a cycle start date before activation"

        empty = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Lifecycle Empty {suffix}",
                "duration_days": 1,
                "start_date": "2026-09-10",
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:30:00"}],
            },
        ).json()
        blocked_validation = client.post(f"/api/meal-cycles/{empty['id']}/activate")
        assert blocked_validation.status_code == 409
        detail = blocked_validation.json()["detail"]
        assert detail["message"] == "Meal Cycle has blocking validation errors"
        assert detail["error_count"] == 1
        assert detail["issues"][0]["code"] == "EMPTY_SLOT"

        assert client.delete(f"/api/meal-cycles/{unscheduled['id']}").status_code == 204
        assert client.delete(f"/api/meal-cycles/{empty['id']}").status_code == 204
