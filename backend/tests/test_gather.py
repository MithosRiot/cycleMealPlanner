from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _lot(client: TestClient, ingredient_id: int, location_id: int, unit_id: int, quantity: str, expiration_date: str) -> dict:
    response = client.post("/api/inventory", json={
        "ingredient_id": ingredient_id, "location_id": location_id, "quantity": quantity, "unit_id": unit_id,
        "purchase_date": "2026-09-01", "opened_date": None, "expiration_date": expiration_date,
        "frozen_date": None, "thawed_date": None, "notes": None, "transaction_type": "MANUAL_ADD",
    })
    assert response.status_code == 201
    return response.json()


def test_exact_lot_gather_suggestions_override_validation_and_read_only_inventory() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Gather Ingredient {suffix}", "shopping_category_id": None,
            "preferred_unit_id": units["each"]["id"], "default_location_id": location["id"],
            "perishable": True, "notes": None, "aliases": [],
        }).json()
        first = _lot(client, ingredient["id"], location["id"], units["each"]["id"], "1", "2026-09-10")
        second = _lot(client, ingredient["id"], location["id"], units["each"]["id"], "2", "2026-09-12")
        expired = _lot(client, ingredient["id"], location["id"], units["each"]["id"], "5", "2026-09-03")

        recipe = client.post("/api/recipes", json={
            "name": f"Gather Recipe {suffix}", "description": None, "base_servings": "4", "serving_unit": "servings",
            "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": None, "cook_time_minutes": None,
            "notes": None, "favorite": False, "meal_types": ["DINNER"], "tag_ids": [],
            "ingredients": [{"ingredient_id": ingredient["id"], "quantity": "2", "unit_id": units["each"]["id"],
                             "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None}],
        }).json()
        meal = client.post("/api/meals", json={
            "name": f"Gather Meal {suffix}", "description": None, "favorite": False, "meal_types": ["DINNER"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Gather Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]})
        assert placed.status_code == 201

        gather = client.get(f"/api/meal-cycles/{cycle['id']}/gather")
        assert gather.status_code == 200
        requirement = gather.json()["requirements"][0]
        assert expired["id"] not in [row["lot_id"] for row in requirement["candidates"]]
        assert [row["lot_id"] for row in requirement["suggestions"]] == [first["id"], second["id"]]

        applied = client.post(f"/api/meal-cycles/{cycle['id']}/gather/apply-suggestions")
        assert applied.status_code == 200
        requirement = applied.json()["requirements"][0]
        assert len(requirement["selections"]) == 2
        assert Decimal(requirement["selected_quantity"]) == Decimal("2")
        assert Decimal(requirement["shortage_quantity"]) == Decimal("0")

        path = f"/api/meal-cycles/{cycle['id']}/gather/{requirement['planned_meal_id']}/{requirement['meal_recipe_id']}/{requirement['recipe_ingredient_id']}"
        rejected_expired = client.put(path, json={"selections": [{"lot_id": expired["id"], "quantity": "1"}]})
        assert rejected_expired.status_code == 422
        rejected_over = client.put(path, json={"selections": [{"lot_id": second["id"], "quantity": "3"}]})
        assert rejected_over.status_code == 422
        override = client.put(path, json={"selections": [{"lot_id": second["id"], "quantity": "2"}]})
        assert override.status_code == 200
        assert [row["lot_id"] for row in override.json()["requirements"][0]["selections"]] == [second["id"]]

        for lot, expected in [(first, "1"), (second, "2"), (expired, "5")]:
            detail = client.get(f"/api/inventory/{lot['id']}").json()
            assert Decimal(detail["quantity"]) == Decimal(expected)
            assert len(detail["transactions"]) == 1

        removed = client.delete(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal")
        assert removed.status_code == 204
        after = client.get(f"/api/meal-cycles/{cycle['id']}/gather").json()
        assert after["requirements"] == []
