from fastapi.testclient import TestClient

from app.main import app


def test_meal_cycle_crud_and_slot_generation() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/meal-cycles",
            json={
                "name": "Two Week Dinner Cycle",
                "duration_days": 14,
                "start_date": None,
                "notes": "Draft cycle",
                "slot_definitions": [
                    {"label": "Breakfast", "sort_order": 0},
                    {"label": "Dinner", "sort_order": 10},
                ],
            },
        )
        assert created.status_code == 201
        cycle = created.json()
        cycle_id = cycle["id"]
        assert cycle["status"] == "DRAFT"
        assert cycle["start_date"] is None
        assert cycle["duration_days"] == 14
        assert [item["label"] for item in cycle["slot_definitions"]] == ["Breakfast", "Dinner"]
        assert len(cycle["slots"]) == 28
        assert [(item["day_number"], item["sort_order"]) for item in cycle["slots"][:4]] == [
            (1, 0),
            (1, 10),
            (2, 0),
            (2, 10),
        ]

        listed = client.get("/api/meal-cycles")
        assert listed.status_code == 200
        assert cycle_id in {item["id"] for item in listed.json()}

        updated = client.put(
            f"/api/meal-cycles/{cycle_id}",
            json={
                "name": "Weeknight Cycle",
                "duration_days": 5,
                "start_date": "2026-09-01",
                "notes": None,
                "slot_definitions": [
                    {"label": "Lunch", "sort_order": 0},
                    {"label": "Dinner", "sort_order": 1},
                    {"label": "Snack", "sort_order": 2},
                ],
            },
        )
        assert updated.status_code == 200
        changed = updated.json()
        assert changed["name"] == "Weeknight Cycle"
        assert changed["start_date"] == "2026-09-01"
        assert [item["label"] for item in changed["slot_definitions"]] == ["Lunch", "Dinner", "Snack"]
        assert len(changed["slots"]) == 15

        deleted = client.delete(f"/api/meal-cycles/{cycle_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/meal-cycles/{cycle_id}").status_code == 404


def test_meal_cycle_validates_slots_and_name_uniqueness() -> None:
    with TestClient(app) as client:
        payload = {
            "name": "Validation Cycle",
            "duration_days": 7,
            "start_date": None,
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
        }
        assert client.post("/api/meal-cycles", json=payload).status_code == 201
        assert client.post("/api/meal-cycles", json=payload).status_code == 409

        duplicate_label = {
            "name": "Duplicate Slot Labels",
            "duration_days": 7,
            "start_date": None,
            "notes": None,
            "slot_definitions": [
                {"label": "Dinner", "sort_order": 0},
                {"label": " dinner ", "sort_order": 1},
            ],
        }
        response = client.post("/api/meal-cycles", json=duplicate_label)
        assert response.status_code == 400

        duplicate_order = {
            "name": "Duplicate Slot Order",
            "duration_days": 7,
            "start_date": None,
            "notes": None,
            "slot_definitions": [
                {"label": "Lunch", "sort_order": 0},
                {"label": "Dinner", "sort_order": 0},
            ],
        }
        response = client.post("/api/meal-cycles", json=duplicate_order)
        assert response.status_code == 400
