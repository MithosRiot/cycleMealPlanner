from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _unit(client: TestClient, code: str = "each") -> dict:
    return next(row for row in client.get("/api/reference/units").json() if row["code"] == code)


def _location(client: TestClient, kind: str = "REFRIGERATOR") -> dict:
    return next(row for row in client.get("/api/reference/inventory-locations").json() if row["active"] and row["location_type"] == kind)


def _cycle(client: TestClient, name: str) -> dict:
    response = client.post("/api/meal-cycles", json={
        "name": name,
        "duration_days": 2,
        "start_date": "2026-09-07",
        "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00"}],
    })
    assert response.status_code == 201
    return response.json()


def _ingredient(client: TestClient, name: str) -> dict:
    unit = _unit(client)
    location = _location(client)
    response = client.post("/api/ingredients", json={
        "name": name,
        "shopping_category_id": None,
        "preferred_unit_id": unit["id"],
        "default_location_id": location["id"],
        "perishable": True,
        "notes": None,
        "aliases": [],
    })
    assert response.status_code == 201
    return response.json()


def test_unlinked_manual_item_survives_regeneration_and_closes_without_inventory() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle = _cycle(client, f"Manual Shopping Cycle {suffix}")
        before_inventory = len(client.get("/api/inventory?include_empty=true").json())

        created = client.post(f"/api/shopping/{cycle['id']}/manual-items", json={
            "name": "Paper towels",
            "quantity": "2",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": "Manual household item",
        })
        assert created.status_code == 201
        item = created.json()["items"][0]
        assert item["name"] == "Paper towels"
        assert item["status"] == "PENDING"
        assert item["ingredient_id"] is None

        updated = client.put(f"/api/shopping/{cycle['id']}/manual-items/{item['id']}", json={
            "name": "Paper towels - large rolls",
            "quantity": "3",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": "Updated before shopping",
        })
        assert updated.status_code == 200
        assert updated.json()["items"][0]["quantity"] == "3.000000"

        regenerated = client.post(f"/api/shopping/{cycle['id']}/regenerate")
        assert regenerated.status_code == 200
        manual_after_regenerate = client.get(f"/api/shopping/{cycle['id']}/manual-items").json()["items"]
        assert len(manual_after_regenerate) == 1
        assert manual_after_regenerate[0]["name"] == "Paper towels - large rolls"
        assert manual_after_regenerate[0]["status"] == "PENDING"

        completed = client.post(f"/api/shopping/{cycle['id']}/manual-items/{item['id']}/complete", json={
            "inventory_quantity": None,
            "inventory_unit_id": None,
            "storage_location_id": None,
            "purchase_date": None,
            "expiration_date": None,
            "inventory_notes": None,
        })
        assert completed.status_code == 200
        completed_item = completed.json()["items"][0]
        assert completed_item["status"] == "COMPLETED"
        assert completed_item["completed_at"] is not None
        assert completed_item["inventory_lot_id"] is None
        assert len(client.get("/api/inventory?include_empty=true").json()) == before_inventory

        blocked_edit = client.put(f"/api/shopping/{cycle['id']}/manual-items/{item['id']}", json={
            "name": "Should fail",
            "quantity": "1",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": None,
        })
        assert blocked_edit.status_code == 409


def test_ingredient_linked_manual_completion_creates_inventory_exactly_once_and_skip_is_durable() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle = _cycle(client, f"Linked Manual Shopping Cycle {suffix}")
        ingredient = _ingredient(client, f"Manual Shopping Apples {suffix}")
        unit = _unit(client)
        location = _location(client)

        created = client.post(f"/api/shopping/{cycle['id']}/manual-items", json={
            "name": "Extra apples for snacks",
            "quantity": "6",
            "unit_id": unit["id"],
            "shopping_category_id": None,
            "ingredient_id": ingredient["id"],
            "notes": "Linked manual purchase",
        })
        assert created.status_code == 201
        item_id = created.json()["items"][0]["id"]

        incomplete_intake = client.post(f"/api/shopping/{cycle['id']}/manual-items/{item_id}/complete", json={
            "inventory_quantity": "6",
            "inventory_unit_id": unit["id"],
            "storage_location_id": None,
            "purchase_date": "2026-09-07",
            "expiration_date": "2026-09-14",
            "inventory_notes": "Should reject partial intake",
        })
        assert incomplete_intake.status_code == 422

        completed = client.post(f"/api/shopping/{cycle['id']}/manual-items/{item_id}/complete", json={
            "inventory_quantity": "6",
            "inventory_unit_id": unit["id"],
            "storage_location_id": location["id"],
            "purchase_date": "2026-09-07",
            "expiration_date": "2026-09-14",
            "inventory_notes": "Manual Shopping linked intake",
        })
        assert completed.status_code == 200
        row = completed.json()["items"][0]
        lot_id = row["inventory_lot_id"]
        assert row["status"] == "COMPLETED"
        assert lot_id is not None
        assert row["storage_location_id"] == location["id"]

        lots = [lot for lot in client.get(f"/api/inventory?ingredient_id={ingredient['id']}&include_empty=true").json() if lot["id"] == lot_id]
        assert len(lots) == 1
        assert lots[0]["quantity"] == "6.000000"
        assert lots[0]["purchase_date"] == "2026-09-07"
        assert lots[0]["expiration_date"] == "2026-09-14"

        repeat = client.post(f"/api/shopping/{cycle['id']}/manual-items/{item_id}/complete", json={
            "inventory_quantity": "6",
            "inventory_unit_id": unit["id"],
            "storage_location_id": location["id"],
            "purchase_date": "2026-09-07",
            "expiration_date": "2026-09-14",
            "inventory_notes": "Duplicate retry",
        })
        assert repeat.status_code == 200
        assert repeat.json()["items"][0]["inventory_lot_id"] == lot_id
        same_lot = [lot for lot in client.get(f"/api/inventory?ingredient_id={ingredient['id']}&include_empty=true").json() if lot["id"] == lot_id]
        assert len(same_lot) == 1

        history = client.get(f"/api/history/inventory?ingredient_id={ingredient['id']}&lot_id={lot_id}&transaction_type=PURCHASE")
        assert history.status_code == 200
        assert len(history.json()) == 1
        assert history.json()[0]["quantity_delta"] == "6.000000"
        assert history.json()[0]["note"] == "Manual Shopping item: Extra apples for snacks"

        skipped = client.post(f"/api/shopping/{cycle['id']}/manual-items", json={
            "name": "Disposable plates",
            "quantity": "1",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": None,
        }).json()["items"]
        skip_id = next(item["id"] for item in skipped if item["name"] == "Disposable plates")
        skip_response = client.post(f"/api/shopping/{cycle['id']}/manual-items/{skip_id}/skip")
        assert skip_response.status_code == 200
        skipped_item = next(item for item in skip_response.json()["items"] if item["id"] == skip_id)
        assert skipped_item["status"] == "SKIPPED"
        assert skipped_item["completed_at"] is not None
        assert client.post(f"/api/shopping/{cycle['id']}/regenerate").status_code == 200
        durable = next(item for item in client.get(f"/api/shopping/{cycle['id']}/manual-items").json()["items"] if item["id"] == skip_id)
        assert durable["status"] == "SKIPPED"
