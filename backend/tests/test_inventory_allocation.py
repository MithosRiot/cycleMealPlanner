from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _lot(client: TestClient, ingredient_id: int, location_id: int, unit_id: int, quantity: str, **dates) -> dict:
    response = client.post("/api/inventory", json={
        "ingredient_id": ingredient_id,
        "location_id": location_id,
        "quantity": quantity,
        "unit_id": unit_id,
        "purchase_date": dates.get("purchase_date"),
        "opened_date": dates.get("opened_date"),
        "expiration_date": dates.get("expiration_date"),
        "frozen_date": dates.get("frozen_date"),
        "thawed_date": dates.get("thawed_date"),
        "notes": None,
        "transaction_type": "MANUAL_ADD",
    })
    assert response.status_code == 201
    return response.json()


def test_allocation_priority_expiration_state_location_and_partial_split_is_read_only() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        locations = {item["name"]: item for item in client.get("/api/reference/inventory-locations").json()}
        pantry = locations["Pantry"]
        other_location = next(item for item in locations.values() if item["id"] != pantry["id"])
        ingredient = client.post("/api/ingredients", json={
            "name": f"Allocation Flour {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": units["lb"]["id"],
            "default_location_id": pantry["id"],
            "perishable": True,
            "notes": None,
            "aliases": [],
        }).json()

        expired = _lot(client, ingredient["id"], pantry["id"], units["lb"]["id"], "1", purchase_date="2026-07-01", expiration_date="2026-08-31")
        opened_thawed = _lot(client, ingredient["id"], pantry["id"], units["lb"]["id"], "1", purchase_date="2026-08-05", opened_date="2026-08-20", expiration_date="2026-09-10", frozen_date="2026-08-01", thawed_date="2026-08-19")
        opened_frozen = _lot(client, ingredient["id"], pantry["id"], units["lb"]["id"], "1", purchase_date="2026-08-01", opened_date="2026-08-20", expiration_date="2026-09-10", frozen_date="2026-08-01")
        unopened_thawed = _lot(client, ingredient["id"], pantry["id"], units["lb"]["id"], "1", purchase_date="2026-07-25", expiration_date="2026-09-10", frozen_date="2026-08-01", thawed_date="2026-08-18")
        nonpreferred = _lot(client, ingredient["id"], other_location["id"], units["lb"]["id"], "1", purchase_date="2026-08-10", expiration_date="2026-09-15")
        preferred = _lot(client, ingredient["id"], pantry["id"], units["lb"]["id"], "1", purchase_date="2026-08-10", expiration_date="2026-09-15")
        undated = _lot(client, ingredient["id"], pantry["id"], units["lb"]["id"], "1", purchase_date="2026-07-01")

        preview = client.post("/api/inventory-allocation/preview", json={
            "ingredient_id": ingredient["id"],
            "quantity": "4.5",
            "unit_id": units["lb"]["id"],
            "use_date": "2026-09-01",
        })
        assert preview.status_code == 200
        body = preview.json()
        ids = [row["lot_id"] for row in body["allocations"]]
        assert expired["id"] not in ids
        assert ids[:3] == [opened_thawed["id"], opened_frozen["id"], unopened_thawed["id"]]
        assert ids[3:5] == [preferred["id"], nonpreferred["id"]]
        assert undated["id"] not in ids
        assert Decimal(body["allocated_quantity"]) == Decimal("4.5")
        assert Decimal(body["shortage_quantity"]) == Decimal("0")
        assert Decimal(body["allocations"][-1]["allocated_quantity"]) == Decimal("0.5")

        for lot in [expired, opened_thawed, opened_frozen, unopened_thawed, nonpreferred, preferred, undated]:
            detail = client.get(f"/api/inventory/{lot['id']}").json()
            assert Decimal(detail["quantity"]) == Decimal("1")
            assert len(detail["transactions"]) == 1


def test_cycle_allocation_does_not_double_count_own_reservations() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        locations = client.get("/api/reference/inventory-locations").json()
        location = locations[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Cycle Allocation Ingredient {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": units["each"]["id"],
            "default_location_id": location["id"],
            "perishable": True,
            "notes": None,
            "aliases": [],
        }).json()
        lot = _lot(client, ingredient["id"], location["id"], units["each"]["id"], "3", expiration_date="2026-09-10")

        recipe = client.post("/api/recipes", json={
            "name": f"Cycle Allocation Recipe {suffix}",
            "description": None,
            "base_servings": "4",
            "serving_unit": "servings",
            "yield_quantity": None,
            "yield_unit_id": None,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
            "notes": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "ingredients": [{
                "ingredient_id": ingredient["id"],
                "quantity": "2",
                "unit_id": units["each"]["id"],
                "optional": False,
                "scaling_mode": "LINEAR",
                "required_state": "ANY",
                "sort_order": 0,
                "notes": None,
            }],
        }).json()
        meal = client.post("/api/meals", json={
            "name": f"Cycle Allocation Meal {suffix}",
            "description": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Cycle Allocation {suffix}",
            "duration_days": 1,
            "start_date": "2026-09-05",
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        assert client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]}).status_code == 201
        assert client.post(f"/api/meal-cycles/{cycle['id']}/reservations/regenerate").status_code == 200

        preview = client.get(f"/api/meal-cycles/{cycle['id']}/allocation-preview")
        assert preview.status_code == 200
        requirement = preview.json()["requirements"][0]
        assert Decimal(requirement["requested_quantity"]) == Decimal("2")
        assert Decimal(requirement["reserved_elsewhere_quantity"]) == Decimal("0")
        assert Decimal(requirement["allocated_quantity"]) == Decimal("2")
        assert Decimal(requirement["shortage_quantity"]) == Decimal("0")
        assert requirement["allocations"][0]["lot_id"] == lot["id"]
        assert requirement["use_date"] == "2026-09-05"
