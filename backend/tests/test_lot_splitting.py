from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_split_lot_preserves_quantity_metadata_history_and_allocation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        locations = client.get("/api/reference/inventory-locations").json()
        pantry = next(item for item in locations if item["name"] == "Pantry")
        target = next(item for item in locations if item["id"] != pantry["id"])

        ingredient = client.post("/api/ingredients", json={
            "name": f"Split Ingredient {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": units["lb"]["id"],
            "default_location_id": pantry["id"],
            "perishable": True,
            "notes": None,
            "aliases": [],
        })
        assert ingredient.status_code == 201
        ingredient_id = ingredient.json()["id"]

        created = client.post("/api/inventory", json={
            "ingredient_id": ingredient_id,
            "location_id": pantry["id"],
            "quantity": "10",
            "unit_id": units["lb"]["id"],
            "purchase_date": "2026-08-01",
            "opened_date": "2026-08-10",
            "expiration_date": "2026-09-20",
            "frozen_date": "2026-08-02",
            "thawed_date": "2026-08-15",
            "notes": "Original lot notes",
            "transaction_type": "PURCHASE",
        })
        assert created.status_code == 201
        source_id = created.json()["id"]

        before_availability = next(
            row for row in client.get("/api/inventory-availability").json()
            if row["ingredient_id"] == ingredient_id
        )
        assert Decimal(before_availability["physical_quantity"]) == Decimal("10")

        split = client.post(f"/api/inventory/{source_id}/split", json={
            "quantity": "3.5",
            "to_location_id": target["id"],
            "note": "Move portion for prep",
        })
        assert split.status_code == 201
        body = split.json()
        source = body["source"]
        child = body["child"]

        assert Decimal(source["quantity"]) == Decimal("6.5")
        assert Decimal(child["quantity"]) == Decimal("3.5")
        assert Decimal(source["quantity"]) + Decimal(child["quantity"]) == Decimal("10")
        assert child["ingredient_id"] == source["ingredient_id"] == ingredient_id
        assert child["unit_id"] == source["unit_id"] == units["lb"]["id"]
        assert child["location_id"] == target["id"]
        assert child["purchase_date"] == "2026-08-01"
        assert child["opened_date"] == "2026-08-10"
        assert child["expiration_date"] == "2026-09-20"
        assert child["frozen_date"] == "2026-08-02"
        assert child["thawed_date"] == "2026-08-15"
        assert child["notes"] == "Original lot notes"

        source_split = source["transactions"][-1]
        child_split = child["transactions"][-1]
        assert source_split["transaction_type"] == "TRANSFER"
        assert Decimal(source_split["quantity_delta"]) == Decimal("-3.5")
        assert f"lot #{child['id']}" in source_split["note"]
        assert "Move portion for prep" in source_split["note"]
        assert source_split["from_location_id"] == pantry["id"]
        assert source_split["to_location_id"] == target["id"]
        assert child_split["transaction_type"] == "TRANSFER"
        assert Decimal(child_split["quantity_delta"]) == Decimal("3.5")
        assert f"lot #{source_id}" in child_split["note"]
        assert child_split["from_location_id"] == pantry["id"]
        assert child_split["to_location_id"] == target["id"]

        after_availability = next(
            row for row in client.get("/api/inventory-availability").json()
            if row["ingredient_id"] == ingredient_id
        )
        assert Decimal(after_availability["physical_quantity"]) == Decimal("10")
        assert Decimal(after_availability["reserved_quantity"]) == Decimal(before_availability["reserved_quantity"])
        assert Decimal(after_availability["available_quantity"]) == Decimal(before_availability["available_quantity"])

        allocation = client.post("/api/inventory-allocation/preview", json={
            "ingredient_id": ingredient_id,
            "quantity": "10",
            "unit_id": units["lb"]["id"],
            "use_date": "2026-09-01",
            "exclude_cycle_id": None,
        })
        assert allocation.status_code == 200
        allocated_ids = [row["lot_id"] for row in allocation.json()["allocations"]]
        assert set(allocated_ids) == {source_id, child["id"]}
        assert Decimal(allocation.json()["allocated_quantity"]) == Decimal("10")
        assert Decimal(allocation.json()["shortage_quantity"]) == Decimal("0")


def test_split_validation_and_whole_lot_transfer_remain_safe() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        locations = client.get("/api/reference/inventory-locations").json()
        source_location = locations[0]
        target_location = next(item for item in locations if item["id"] != source_location["id"])

        ingredient = client.post("/api/ingredients", json={
            "name": f"Split Validation {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": units["each"]["id"],
            "default_location_id": source_location["id"],
            "perishable": False,
            "notes": None,
            "aliases": [],
        }).json()
        lot = client.post("/api/inventory", json={
            "ingredient_id": ingredient["id"],
            "location_id": source_location["id"],
            "quantity": "5",
            "unit_id": units["each"]["id"],
            "purchase_date": None,
            "opened_date": None,
            "expiration_date": None,
            "frozen_date": None,
            "thawed_date": None,
            "notes": None,
            "transaction_type": "MANUAL_ADD",
        }).json()
        lot_id = lot["id"]

        zero = client.post(f"/api/inventory/{lot_id}/split", json={"quantity": "0", "to_location_id": target_location["id"]})
        assert zero.status_code == 422
        full = client.post(f"/api/inventory/{lot_id}/split", json={"quantity": "5", "to_location_id": target_location["id"]})
        assert full.status_code == 409
        too_much = client.post(f"/api/inventory/{lot_id}/split", json={"quantity": "6", "to_location_id": target_location["id"]})
        assert too_much.status_code == 409

        unchanged = client.get(f"/api/inventory/{lot_id}").json()
        assert Decimal(unchanged["quantity"]) == Decimal("5")
        assert len(unchanged["transactions"]) == 1
        all_lots = client.get(f"/api/inventory?ingredient_id={ingredient['id']}&include_empty=true").json()
        assert len(all_lots) == 1

        moved = client.post(f"/api/inventory/{lot_id}/transfer", json={
            "to_location_id": target_location["id"],
            "note": "Whole lot move",
        })
        assert moved.status_code == 200
        assert moved.json()["id"] == lot_id
        assert moved.json()["location_id"] == target_location["id"]
        assert Decimal(moved.json()["quantity"]) == Decimal("5")
        after_move_lots = client.get(f"/api/inventory?ingredient_id={ingredient['id']}&include_empty=true").json()
        assert len(after_move_lots) == 1
        detail = client.get(f"/api/inventory/{lot_id}").json()
        assert detail["transactions"][-1]["transaction_type"] == "TRANSFER"
        assert Decimal(detail["transactions"][-1]["quantity_delta"]) == Decimal("0")
        assert detail["transactions"][-1]["note"] == "Whole lot move"
