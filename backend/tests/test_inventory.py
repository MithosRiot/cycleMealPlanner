from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app


def _refs(client: TestClient) -> tuple[int, int, int, int]:
    ingredient = client.post(
        "/api/ingredients",
        json={
            "name": "Inventory Test Rice",
            "shopping_category_id": None,
            "preferred_unit_id": None,
            "default_location_id": None,
            "perishable": False,
            "notes": None,
            "aliases": [],
        },
    ).json()
    units = client.get("/api/reference/units").json()
    each_id = next(unit["id"] for unit in units if unit["code"] == "each")
    locations = client.get("/api/reference/inventory-locations").json()
    pantry_id = next(item["id"] for item in locations if item["name"] == "Pantry")
    fridge_id = next(item["id"] for item in locations if item["name"] == "Refrigerator")
    return ingredient["id"], each_id, pantry_id, fridge_id


def test_inventory_lifecycle_records_transactions_and_prevents_negative_quantity() -> None:
    with TestClient(app) as client:
        ingredient_id, unit_id, pantry_id, fridge_id = _refs(client)
        created = client.post(
            "/api/inventory",
            json={
                "ingredient_id": ingredient_id,
                "location_id": pantry_id,
                "quantity": "5",
                "unit_id": unit_id,
                "purchase_date": "2026-08-29",
                "expiration_date": "2026-09-15",
                "notes": "Initial purchase",
                "transaction_type": "PURCHASE",
            },
        )
        assert created.status_code == 201
        lot_id = created.json()["id"]
        assert Decimal(created.json()["quantity"]) == Decimal("5")

        added = client.post(f"/api/inventory/{lot_id}/add", json={"quantity": "2", "note": "Found extra"})
        assert Decimal(added.json()["quantity"]) == Decimal("7")

        removed = client.post(f"/api/inventory/{lot_id}/remove", json={"quantity": "3", "note": "Used"})
        assert Decimal(removed.json()["quantity"]) == Decimal("4")

        blocked = client.post(f"/api/inventory/{lot_id}/remove", json={"quantity": "10"})
        assert blocked.status_code == 409

        corrected = client.post(f"/api/inventory/{lot_id}/correct", json={"quantity": "3.5", "note": "Counted"})
        assert Decimal(corrected.json()["quantity"]) == Decimal("3.5")

        moved = client.post(f"/api/inventory/{lot_id}/transfer", json={"to_location_id": fridge_id, "note": "Moved"})
        assert moved.status_code == 200
        assert moved.json()["location_id"] == fridge_id

        detail = client.get(f"/api/inventory/{lot_id}")
        assert detail.status_code == 200
        types = [item["transaction_type"] for item in detail.json()["transactions"]]
        assert types == ["PURCHASE", "MANUAL_ADD", "MANUAL_REMOVE", "CORRECTION", "TRANSFER"]

        by_ingredient = client.get("/api/inventory", params={"ingredient_id": ingredient_id})
        assert [item["id"] for item in by_ingredient.json()] == [lot_id]
        by_location = client.get("/api/inventory", params={"location_id": fridge_id})
        assert [item["id"] for item in by_location.json()] == [lot_id]
