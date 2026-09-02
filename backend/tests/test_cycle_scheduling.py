from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_cycle_schedule_updates_dates_and_times_without_rebuilding_slots() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        created = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Scheduled Cycle {suffix}",
                "duration_days": 3,
                "start_date": None,
                "notes": None,
                "slot_definitions": [
                    {"label": "Breakfast", "sort_order": 0, "serving_time": None},
                    {"label": "Dinner", "sort_order": 1, "serving_time": None},
                ],
            },
        )
        assert created.status_code == 201
        cycle = created.json()
        cycle_id = cycle["id"]
        slot_ids = [slot["id"] for slot in cycle["slots"]]
        definitions = {item["label"]: item for item in cycle["slot_definitions"]}

        scheduled = client.put(
            f"/api/meal-cycles/{cycle_id}/schedule",
            json={
                "start_date": "2026-09-10",
                "serving_times": {
                    str(definitions["Breakfast"]["id"]): "08:00:00",
                    str(definitions["Dinner"]["id"]): "18:30:00",
                },
            },
        )
        assert scheduled.status_code == 200
        body = scheduled.json()
        assert body["start_date"] == "2026-09-10"
        assert [slot["id"] for slot in body["slots"]] == slot_ids
        assert next(item for item in body["slot_definitions"] if item["label"] == "Breakfast")["serving_time"] == "08:00:00"
        assert next(item for item in body["slot_definitions"] if item["label"] == "Dinner")["serving_time"] == "18:30:00"

        day_two_breakfast = next(slot for slot in body["slots"] if slot["day_number"] == 2 and slot["sort_order"] == 0)
        assert day_two_breakfast["scheduled_date"] == "2026-09-11"
        assert day_two_breakfast["serving_time"] == "08:00:00"
        assert day_two_breakfast["scheduled_datetime"] == "2026-09-11T08:00:00"

        cleared = client.put(
            f"/api/meal-cycles/{cycle_id}/schedule",
            json={
                "start_date": None,
                "serving_times": {
                    str(definitions["Breakfast"]["id"]): None,
                    str(definitions["Dinner"]["id"]): "18:30:00",
                },
            },
        )
        assert cleared.status_code == 200
        cleared_body = cleared.json()
        assert [slot["id"] for slot in cleared_body["slots"]] == slot_ids
        breakfast_slot = next(slot for slot in cleared_body["slots"] if slot["sort_order"] == 0)
        dinner_slot = next(slot for slot in cleared_body["slots"] if slot["sort_order"] == 1)
        assert breakfast_slot["scheduled_date"] is None
        assert breakfast_slot["serving_time"] is None
        assert breakfast_slot["scheduled_datetime"] is None
        assert dinner_slot["scheduled_date"] is None
        assert dinner_slot["serving_time"] == "18:30:00"
        assert dinner_slot["scheduled_datetime"] is None

        unknown = client.put(
            f"/api/meal-cycles/{cycle_id}/schedule",
            json={"start_date": "2026-09-10", "serving_times": {"999999": "12:00:00"}},
        )
        assert unknown.status_code == 422
