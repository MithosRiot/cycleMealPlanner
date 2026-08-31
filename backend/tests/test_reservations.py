from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_reservation_reconcile_availability_and_planned_meal_cleanup() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        each = next(item for item in units if item["code"] == "each")
        location = client.get("/api/reference/inventory-locations").json()[0]

        ingredient_response = client.post("/api/ingredients", json={
            "name": f"Reservation Ingredient {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": each["id"],
            "default_location_id": location["id"],
            "perishable": False,
            "notes": None,
            "aliases": [],
        })
        assert ingredient_response.status_code == 201
        ingredient_id = ingredient_response.json()["id"]

        recipe_response = client.post("/api/recipes", json={
            "name": f"Reservation Recipe {suffix}",
            "description": None,
            "base_servings": "4",
            "serving_unit": "servings",
            "yield_quantity": None,
            "yield_unit_id": None,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
            "notes": None,
            "favorite": False,
            "meal_types": ["BREAKFAST"],
            "tag_ids": [],
            "ingredients": [{
                "ingredient_id": ingredient_id,
                "quantity": "2",
                "unit_id": each["id"],
                "optional": False,
                "scaling_mode": "LINEAR",
                "required_state": "ANY",
                "sort_order": 0,
                "notes": None,
            }],
        })
        assert recipe_response.status_code == 201
        recipe_id = recipe_response.json()["id"]

        meal_response = client.post("/api/meals", json={
            "name": f"Reservation Meal {suffix}",
            "description": None,
            "favorite": False,
            "meal_types": ["BREAKFAST"],
            "tag_ids": [],
            "recipes": [{
                "recipe_id": recipe_id,
                "serving_multiplier": "1",
                "default_servings": "4",
                "sort_order": 0,
                "notes": None,
            }],
        })
        assert meal_response.status_code == 201
        meal_id = meal_response.json()["id"]

        cycle_response = client.post("/api/meal-cycles", json={
            "name": f"Reservation Cycle {suffix}",
            "duration_days": 1,
            "start_date": None,
            "notes": None,
            "slot_definitions": [{"label": "Breakfast", "sort_order": 0}],
        })
        assert cycle_response.status_code == 201
        cycle = cycle_response.json()
        cycle_id = cycle["id"]
        slot_id = cycle["slots"][0]["id"]

        assigned = client.post(f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal", json={"meal_id": meal_id})
        assert assigned.status_code == 201
        planned_meal_id = assigned.json()["id"]

        first = client.post(f"/api/meal-cycles/{cycle_id}/reservations/regenerate")
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["active_count"] == 1
        reservation = first_body["reservations"][0]
        reservation_id = reservation["id"]
        assert reservation["planned_meal_id"] == planned_meal_id
        assert reservation["ingredient_id"] == ingredient_id
        assert Decimal(reservation["quantity"]) == Decimal("2")

        update = client.put(f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal/planning", json={
            "planned_servings": "8",
            "planned_leftover_servings": "0",
            "component_serving_overrides": {},
        })
        assert update.status_code == 200

        second = client.post(f"/api/meal-cycles/{cycle_id}/reservations/regenerate")
        assert second.status_code == 200
        second_reservation = next(item for item in second.json()["reservations"] if item["status"] == "ACTIVE")
        assert second_reservation["id"] == reservation_id
        assert Decimal(second_reservation["quantity"]) == Decimal("4")

        lot = client.post("/api/inventory", json={
            "ingredient_id": ingredient_id,
            "location_id": location["id"],
            "quantity": "3",
            "unit_id": each["id"],
            "purchase_date": None,
            "opened_date": None,
            "expiration_date": None,
            "frozen_date": None,
            "thawed_date": None,
            "notes": None,
            "transaction_type": "MANUAL_ADD",
        })
        assert lot.status_code == 201
        lot_id = lot.json()["id"]

        availability = client.get("/api/inventory-availability")
        assert availability.status_code == 200
        row = next(item for item in availability.json() if item["ingredient_id"] == ingredient_id)
        assert Decimal(row["physical_quantity"]) == Decimal("3")
        assert Decimal(row["reserved_quantity"]) == Decimal("4")
        assert Decimal(row["available_quantity"]) == Decimal("0")
        assert Decimal(row["shortage_quantity"]) == Decimal("1")

        lot_detail = client.get(f"/api/inventory/{lot_id}")
        assert lot_detail.status_code == 200
        assert Decimal(lot_detail.json()["quantity"]) == Decimal("3")
        assert len(lot_detail.json()["transactions"]) == 1

        removed = client.delete(f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal")
        assert removed.status_code == 204
        after_remove = client.get(f"/api/meal-cycles/{cycle_id}/reservations")
        assert after_remove.status_code == 200
        assert after_remove.json()["active_count"] == 0
        assert after_remove.json()["reservations"] == []
