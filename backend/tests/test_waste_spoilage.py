from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.models.reservation import InventoryReservation


def _create_ingredient_lot(client: TestClient, suffix: str, quantity: str = "5") -> tuple[dict, dict, dict, dict]:
    units = {item["code"]: item for item in client.get("/api/reference/units").json()}
    each = units["each"]
    location = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Pantry")
    ingredient = client.post("/api/ingredients", json={
        "name": f"Discard Ingredient {suffix}",
        "shopping_category_id": None,
        "preferred_unit_id": each["id"],
        "default_location_id": location["id"],
        "perishable": True,
        "notes": None,
        "aliases": [],
    }).json()
    lot = client.post("/api/inventory", json={
        "ingredient_id": ingredient["id"],
        "location_id": location["id"],
        "quantity": quantity,
        "unit_id": each["id"],
        "purchase_date": "2026-09-06",
        "opened_date": None,
        "expiration_date": "2026-09-09",
        "frozen_date": None,
        "thawed_date": None,
        "notes": "Discard regression lot",
        "transaction_type": "PURCHASE",
    }).json()
    return ingredient, lot, each, location


def test_waste_and_spoilage_are_distinct_history_transactions() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        ingredient, lot, _, _ = _create_ingredient_lot(client, suffix)

        waste = client.post(f"/api/inventory/{lot['id']}/waste", json={
            "quantity": "1.25",
            "reason": "Trim loss",
            "note": "Damaged edge removed",
        })
        assert waste.status_code == 200
        assert Decimal(waste.json()["quantity"]) == Decimal("3.75")

        spoilage = client.post(f"/api/inventory/{lot['id']}/spoilage", json={
            "quantity": "0.75",
            "reason": "Visible mold",
            "note": "Discarded after inspection",
        })
        assert spoilage.status_code == 200
        assert Decimal(spoilage.json()["quantity"]) == Decimal("3")

        detail = client.get(f"/api/inventory/{lot['id']}").json()
        waste_tx = next(item for item in detail["transactions"] if item["transaction_type"] == "WASTE")
        spoilage_tx = next(item for item in detail["transactions"] if item["transaction_type"] == "SPOILAGE")
        assert Decimal(waste_tx["quantity_delta"]) == Decimal("-1.25")
        assert waste_tx["reason"] == "Trim loss"
        assert waste_tx["note"] == "Damaged edge removed"
        assert Decimal(spoilage_tx["quantity_delta"]) == Decimal("-0.75")
        assert spoilage_tx["reason"] == "Visible mold"

        history = client.get("/api/history/inventory", params={
            "ingredient_id": ingredient["id"],
            "lot_id": lot["id"],
            "transaction_type": "SPOILAGE",
        })
        assert history.status_code == 200
        assert len(history.json()) == 1
        assert history.json()[0]["reason"] == "Visible mold"
        assert history.json()[0]["note"] == "Discarded after inspection"


def test_spoilage_cannot_reduce_ingredient_stock_below_active_reservations() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        ingredient, lot, each, _ = _create_ingredient_lot(client, suffix)
        recipe = client.post("/api/recipes", json={
            "name": f"Reserved Discard Recipe {suffix}",
            "description": None,
            "base_servings": "4",
            "serving_unit": "servings",
            "yield_quantity": None,
            "yield_unit_id": None,
            "prep_time_minutes": 5,
            "cook_time_minutes": 10,
            "notes": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "prep_groups": [],
            "advance_prep": [],
            "equipment": [],
            "ingredients": [{
                "ingredient_id": ingredient["id"],
                "prep_group_key": None,
                "quantity": "4",
                "unit_id": each["id"],
                "display_text": None,
                "preparation": None,
                "prep_method": None,
                "prep_size": None,
                "prep_state": None,
                "optional": False,
                "scaling_mode": "LINEAR",
                "required_state": "ANY",
                "sort_order": 0,
                "notes": None,
                "substitutions": [],
            }],
        }).json()
        meal = client.post("/api/meals", json={
            "name": f"Reserved Discard Meal {suffix}",
            "description": None,
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "recipes": [{
                "recipe_id": recipe["id"],
                "serving_multiplier": "1",
                "default_servings": "4",
                "sort_order": 0,
                "notes": None,
            }],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Reserved Discard Cycle {suffix}",
            "duration_days": 1,
            "start_date": "2026-09-06",
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        planned = client.post(
            f"/api/meal-cycles/{cycle['id']}/slots/{cycle['slots'][0]['id']}/planned-meal",
            json={"meal_id": meal["id"]},
        ).json()

        with SessionLocal() as db:
            db.add(InventoryReservation(
                household_id=1,
                cycle_id=cycle["id"],
                planned_meal_id=planned["id"],
                meal_recipe_id=planned["scaled_components"][0]["meal_recipe_id"],
                recipe_id=recipe["id"],
                recipe_ingredient_id=planned["scaled_components"][0]["ingredients"][0]["recipe_ingredient_id"],
                ingredient_id=ingredient["id"],
                quantity=Decimal("4"),
                unit_id=each["id"],
                status="ACTIVE",
            ))
            db.commit()

        blocked = client.post(f"/api/inventory/{lot['id']}/spoilage", json={
            "quantity": "2",
            "reason": "Past safe use date",
            "note": None,
        })
        assert blocked.status_code == 409
        assert "4" in blocked.json()["detail"]
        assert Decimal(client.get(f"/api/inventory/{lot['id']}").json()["quantity"]) == Decimal("5")

        allowed = client.post(f"/api/inventory/{lot['id']}/spoilage", json={
            "quantity": "1",
            "reason": "Past safe use date",
            "note": "Only unreserved stock discarded",
        })
        assert allowed.status_code == 200
        assert Decimal(allowed.json()["quantity"]) == Decimal("4")

        availability = client.get("/api/reservations/availability").json()
        row = next(item for item in availability if item["ingredient_id"] == ingredient["id"])
        assert Decimal(row["physical_quantity"]) == Decimal("4")
        assert Decimal(row["reserved_quantity"]) == Decimal("4")
        assert Decimal(row["available_quantity"]) == Decimal("0")
        assert Decimal(row["shortage_quantity"]) == Decimal("0")
