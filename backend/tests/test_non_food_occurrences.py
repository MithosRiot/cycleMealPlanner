from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.session import engine
from app.main import app


def test_non_food_occurrences_persist_without_operational_demand_and_complete_cycle() -> None:
    suffix = uuid4().hex[:8]
    cycle_id: int | None = None
    planned_ids: list[int] = []
    try:
        with TestClient(app) as client:
            cycle_response = client.post("/api/meal-cycles", json={
                "name": f"Non-food Cycle {suffix}",
                "duration_days": 3,
                "start_date": date.today().isoformat(),
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:30:00"}],
            })
            assert cycle_response.status_code == 201
            cycle = cycle_response.json()
            cycle_id = cycle["id"]
            slots = sorted(cycle["slots"], key=lambda row: row["day_number"])

            payloads = [
                {"occurrence_type": "MANUAL", "title": "Family event", "notes": "Food handled elsewhere"},
                {"occurrence_type": "EATING_OUT", "title": "Local restaurant", "notes": "Dinner out"},
                {"occurrence_type": "SKIPPED", "title": None, "notes": "Not eating dinner"},
            ]
            expected_names = ["Family event", "Local restaurant", "Skipped meal"]
            for slot, payload, expected_name in zip(slots, payloads, expected_names, strict=True):
                response = client.post(
                    f"/api/meal-cycles/{cycle_id}/slots/{slot['id']}/planned-occurrence",
                    json=payload,
                )
                assert response.status_code == 201
                body = response.json()
                planned_ids.append(body["id"])
                assert body["source_type"] == payload["occurrence_type"]
                assert body["meal_id"] is None
                assert body["source_recipe_id"] is None
                assert body["snapshot_name"] == expected_name
                assert body["scaled_components"] == "[]"
                assert body["snapshot_components"] == "[]"

            refreshed = client.get(f"/api/meal-cycles/{cycle_id}").json()
            assert [slot["planned_meal"]["source_type"] for slot in sorted(refreshed["slots"], key=lambda row: row["day_number"])] == ["MANUAL", "EATING_OUT", "SKIPPED"]

            reservations = client.post(f"/api/meal-cycles/{cycle_id}/reservations/regenerate")
            assert reservations.status_code == 200
            assert reservations.json()["active_count"] == 0

            shopping = client.post(f"/api/shopping/{cycle_id}/regenerate")
            assert shopping.status_code == 200
            for item in shopping.json()["items"]:
                assert all(row.get("planned_meal_id") not in planned_ids for row in __import__("json").loads(item["source_trace"] or "[]") if isinstance(row, dict))

            prep = client.get(f"/api/meal-cycles/{cycle_id}/prep-schedule")
            assert prep.status_code == 200
            assert all(task["planned_meal_id"] not in planned_ids for task in prep.json()["tasks"])

            gather = client.get(f"/api/meal-cycles/{cycle_id}/gather")
            assert gather.status_code == 200
            assert all(row["planned_meal_id"] not in planned_ids for row in gather.json()["requirements"])

            cooking = client.get(f"/api/meal-cycles/{cycle_id}/cooking-mode")
            assert cooking.status_code == 200
            non_food_cooking = [row for row in cooking.json()["meals"] if row["planned_meal_id"] in planned_ids]
            assert all(row["steps"] == [] and row["components_without_steps"] == [] for row in non_food_cooking)

            for planned_id in planned_ids:
                completion = client.post(f"/api/planned-meals/{planned_id}/completion")
                assert completion.status_code == 200
                assert completion.json()["status"] == "FINALIZED"
                assert completion.json()["usages"] == []

            validation = client.get(f"/api/meal-cycles/{cycle_id}/validate")
            assert validation.status_code == 200
            assert all(issue["code"] != "EMPTY_SLOT" for issue in validation.json()["issues"])

            activated = client.post(f"/api/meal-cycles/{cycle_id}/activate")
            assert activated.status_code == 200
            assert activated.json()["status"] == "ACTIVE"
            completed = client.post(f"/api/meal-cycles/{cycle_id}/complete")
            assert completed.status_code == 200
            assert completed.json()["status"] == "COMPLETED"
    finally:
        if cycle_id is not None:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM meal_cycles WHERE id=:id"), {"id": cycle_id})
