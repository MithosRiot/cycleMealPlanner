from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _make_cycle(client: TestClient, suffix: str, ingredient_id: int, unit_id: int, meal_name: str) -> tuple[int, int]:
    recipe = client.post("/api/recipes", json={
        "name": f"Availability Recipe {meal_name} {suffix}",
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
            "ingredient_id": ingredient_id,
            "quantity": "1",
            "unit_id": unit_id,
            "optional": False,
            "scaling_mode": "LINEAR",
            "required_state": "ANY",
            "sort_order": 0,
            "notes": None,
        }],
    })
    assert recipe.status_code == 201

    meal = client.post("/api/meals", json={
        "name": f"Availability Meal {meal_name} {suffix}",
        "description": None,
        "favorite": False,
        "meal_types": ["DINNER"],
        "tag_ids": [],
        "recipes": [{
            "recipe_id": recipe.json()["id"],
            "serving_multiplier": "1",
            "default_servings": "4",
            "sort_order": 0,
            "notes": None,
        }],
    })
    assert meal.status_code == 201

    cycle = client.post("/api/meal-cycles", json={
        "name": f"Availability Cycle {meal_name} {suffix}",
        "duration_days": 1,
        "start_date": None,
        "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
    })
    assert cycle.status_code == 201
    cycle_data = cycle.json()
    slot_id = cycle_data["slots"][0]["id"]
    placed = client.post(
        f"/api/meal-cycles/{cycle_data['id']}/slots/{slot_id}/planned-meal",
        json={"meal_id": meal.json()["id"]},
    )
    assert placed.status_code == 201
    return cycle_data["id"], slot_id


def test_other_cycle_reservations_reduce_available_stock_without_double_counting_own_cycle() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        locations = {item["name"]: item for item in client.get("/api/reference/inventory-locations").json()}
        categories = {item["name"]: item for item in client.get("/api/reference/shopping-categories").json()}

        ingredient = client.post("/api/ingredients", json={
            "name": f"Shared Availability Flour {suffix}",
            "shopping_category_id": categories["Pantry"]["id"],
            "preferred_unit_id": units["lb"]["id"],
            "default_location_id": locations["Pantry"]["id"],
            "perishable": False,
            "notes": None,
            "aliases": [],
        })
        assert ingredient.status_code == 201
        ingredient_id = ingredient.json()["id"]

        lot = client.post("/api/inventory", json={
            "ingredient_id": ingredient_id,
            "location_id": locations["Pantry"]["id"],
            "quantity": "24",
            "unit_id": units["oz"]["id"],
            "purchase_date": None,
            "opened_date": None,
            "expiration_date": None,
            "frozen_date": None,
            "thawed_date": None,
            "notes": None,
            "transaction_type": "MANUAL_ADD",
        })
        assert lot.status_code == 201

        cycle_a, _ = _make_cycle(client, suffix, ingredient_id, units["lb"]["id"], "A")
        cycle_b, _ = _make_cycle(client, suffix, ingredient_id, units["lb"]["id"], "B")

        reservations = client.post(f"/api/meal-cycles/{cycle_a}/reservations/regenerate")
        assert reservations.status_code == 200
        assert reservations.json()["active_count"] == 1
        assert Decimal(reservations.json()["reservations"][0]["quantity"]) == Decimal("1")

        availability = client.get("/api/inventory-availability")
        assert availability.status_code == 200
        family = units["lb"]["unit_family"]
        row = next(item for item in availability.json() if item["ingredient_id"] == ingredient_id and item["unit_family"] == family)
        assert Decimal(row["physical_quantity"]) == Decimal("1.5")
        assert Decimal(row["reserved_quantity"]) == Decimal("1")
        assert Decimal(row["available_quantity"]) == Decimal("0.5")
        assert Decimal(row["shortage_quantity"]) == Decimal("0")

        shopping_a = client.post(f"/api/shopping/{cycle_a}/regenerate")
        assert shopping_a.status_code == 200
        item_a = shopping_a.json()["items"][0]
        assert Decimal(item_a["required_quantity"]) == Decimal("1")
        assert Decimal(item_a["inventory_quantity"]) == Decimal("1.5")
        assert Decimal(item_a["generated_quantity"]) == Decimal("0")

        shopping_b = client.post(f"/api/shopping/{cycle_b}/regenerate")
        assert shopping_b.status_code == 200
        item_b = shopping_b.json()["items"][0]
        assert Decimal(item_b["required_quantity"]) == Decimal("1")
        assert Decimal(item_b["inventory_quantity"]) == Decimal("0.5")
        assert Decimal(item_b["generated_quantity"]) == Decimal("0.5")
        assert "reserved for other planned cycles" in (item_b["warning"] or "")

        validation_a = client.get(f"/api/meal-cycles/{cycle_a}/validate")
        assert validation_a.status_code == 200
        shortages_a = [issue for issue in validation_a.json()["issues"] if issue["code"] == "INVENTORY_SHORTAGE" and issue["context"].get("ingredient_id") == ingredient_id]
        assert shortages_a == []

        validation_b = client.get(f"/api/meal-cycles/{cycle_b}/validate")
        assert validation_b.status_code == 200
        shortage_b = next(issue for issue in validation_b.json()["issues"] if issue["code"] == "INVENTORY_SHORTAGE" and issue["context"].get("ingredient_id") == ingredient_id)
        context = shortage_b["context"]
        assert Decimal(context["physical_quantity"]) == Decimal("1.5")
        assert Decimal(context["reserved_elsewhere_quantity"]) == Decimal("1")
        assert Decimal(context["inventory_quantity"]) == Decimal("0.5")
        assert Decimal(context["shortage_quantity"]) == Decimal("0.5")

        lot_after = client.get(f"/api/inventory/{lot.json()['id']}")
        assert lot_after.status_code == 200
        assert Decimal(lot_after.json()["quantity"]) == Decimal("24")
        assert len(lot_after.json()["transactions"]) == 1
