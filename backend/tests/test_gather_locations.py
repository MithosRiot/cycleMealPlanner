from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_gather_by_location_combines_repeated_lot_sources_and_shows_incomplete() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        parent = client.get("/api/reference/inventory-locations").json()[0]
        child_response = client.post("/api/reference/inventory-locations", json={
            "parent_location_id": parent["id"], "name": f"Gather Bin {suffix}",
            "location_type": "PANTRY", "sort_order": 1,
        })
        assert child_response.status_code == 201
        child = child_response.json()

        ingredient = client.post("/api/ingredients", json={
            "name": f"Location Gather Ingredient {suffix}", "shopping_category_id": None,
            "preferred_unit_id": units["each"]["id"], "default_location_id": child["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        lot_response = client.post("/api/inventory", json={
            "ingredient_id": ingredient["id"], "location_id": child["id"], "quantity": "4",
            "unit_id": units["each"]["id"], "purchase_date": "2026-09-01", "opened_date": None,
            "expiration_date": None, "frozen_date": None, "thawed_date": None, "notes": None,
            "transaction_type": "MANUAL_ADD",
        })
        assert lot_response.status_code == 201
        lot = lot_response.json()

        recipe = client.post("/api/recipes", json={
            "name": f"Location Gather Recipe {suffix}", "description": None, "base_servings": "4",
            "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
            "prep_time_minutes": None, "cook_time_minutes": None, "notes": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [],
            "ingredients": [{"ingredient_id": ingredient["id"], "quantity": "1", "unit_id": units["each"]["id"],
                             "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None}],
        }).json()
        meal = client.post("/api/meals", json={
            "name": f"Location Gather Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Location Gather Cycle {suffix}", "duration_days": 2, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        for slot in cycle["slots"]:
            placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]})
            assert placed.status_code == 201

        applied = client.post(f"/api/meal-cycles/{cycle['id']}/gather/apply-suggestions")
        assert applied.status_code == 200
        requirements = applied.json()["requirements"]
        assert len(requirements) == 2

        grouped = client.get(f"/api/meal-cycles/{cycle['id']}/gather/by-location")
        assert grouped.status_code == 200
        body = grouped.json()
        assert body["complete"] is True
        assert body["incomplete_requirements"] == []
        assert len(body["locations"]) == 1
        location = body["locations"][0]
        assert location["location_id"] == child["id"]
        assert location["location_path"].endswith(f"{parent['name']} / Gather Bin {suffix}")
        assert len(location["picks"]) == 1
        pick = location["picks"][0]
        assert pick["lot_id"] == lot["id"]
        assert Decimal(pick["quantity"]) == Decimal("2")
        assert len(pick["sources"]) == 2
        assert [row["day_number"] for row in pick["sources"]] == [1, 2]

        first = requirements[0]
        clear_path = f"/api/meal-cycles/{cycle['id']}/gather/{first['planned_meal_id']}/{first['meal_recipe_id']}/{first['recipe_ingredient_id']}"
        assert client.put(clear_path, json={"selections": []}).status_code == 200
        after = client.get(f"/api/meal-cycles/{cycle['id']}/gather/by-location").json()
        assert after["complete"] is False
        assert len(after["incomplete_requirements"]) == 1
        assert Decimal(after["incomplete_requirements"][0]["remaining_quantity"]) == Decimal("1")
        assert Decimal(after["locations"][0]["picks"][0]["quantity"]) == Decimal("1")
        assert len(after["locations"][0]["picks"][0]["sources"]) == 1

        detail = client.get(f"/api/inventory/{lot['id']}").json()
        assert Decimal(detail["quantity"]) == Decimal("4")
        assert len(detail["transactions"]) == 1
