from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_recipe_prep_groups_round_trip_and_scale_metadata() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        ingredient = client.post(
            "/api/ingredients",
            json={"name": f"Prep Onion {suffix}", "shopping_category_id": None, "preferred_unit_id": units["each"], "default_location_id": None, "perishable": True, "notes": None, "aliases": []},
        ).json()
        created = client.post(
            "/api/recipes",
            json={
                "name": f"Prep Recipe {suffix}",
                "description": None,
                "base_servings": "4",
                "serving_unit": "servings",
                "yield_quantity": None,
                "yield_unit_id": None,
                "prep_time_minutes": 10,
                "cook_time_minutes": 20,
                "notes": None,
                "favorite": False,
                "meal_types": ["DINNER"],
                "tag_ids": [],
                "prep_groups": [
                    {"client_key": "veg", "name": "Vegetables", "sort_order": 0},
                    {"client_key": "finish", "name": "Finish", "sort_order": 1},
                ],
                "ingredients": [{
                    "ingredient_id": ingredient["id"],
                    "prep_group_key": "veg",
                    "quantity": "2",
                    "unit_id": units["each"],
                    "display_text": None,
                    "preparation": "diced",
                    "prep_method": "dice",
                    "prep_size": "1/2-inch",
                    "prep_state": "peeled",
                    "optional": False,
                    "scaling_mode": "LINEAR",
                    "required_state": "FRESH",
                    "sort_order": 0,
                    "notes": "Keep separate",
                }],
            },
        )
        assert created.status_code == 201
        recipe = created.json()
        assert [group["name"] for group in recipe["prep_groups"]] == ["Vegetables", "Finish"]
        veg_id = recipe["prep_groups"][0]["id"]
        row = recipe["ingredients"][0]
        assert row["prep_group_id"] == veg_id
        assert row["prep_method"] == "dice"
        assert row["prep_size"] == "1/2-inch"
        assert row["prep_state"] == "peeled"

        scaled = client.post(f"/api/recipes/{recipe['id']}/scale", json={"requested_servings": "8", "unit_overrides": {}})
        assert scaled.status_code == 200
        scaled_row = scaled.json()["ingredients"][0]
        assert scaled_row["quantity"] == "4.000000"
        assert scaled_row["prep_group_id"] == veg_id
        assert scaled_row["preparation"] == "diced"
        assert scaled_row["prep_method"] == "dice"
        assert scaled_row["prep_size"] == "1/2-inch"
        assert scaled_row["prep_state"] == "peeled"

        updated = client.put(
            f"/api/recipes/{recipe['id']}",
            json={
                "name": recipe["name"], "description": None, "base_servings": "4", "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": 10, "cook_time_minutes": 20, "notes": None, "favorite": False, "meal_types": ["DINNER"], "tag_ids": [],
                "prep_groups": [{"client_key": "finish", "name": "Finish first", "sort_order": 0}],
                "ingredients": [{"ingredient_id": ingredient["id"], "prep_group_key": "finish", "quantity": "2", "unit_id": units["each"], "display_text": None, "preparation": None, "prep_method": "slice", "prep_size": "thin", "prep_state": None, "optional": False, "scaling_mode": "LINEAR", "required_state": "FRESH", "sort_order": 0, "notes": None}],
                "active": True,
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert [group["name"] for group in body["prep_groups"]] == ["Finish first"]
        assert body["ingredients"][0]["prep_group_id"] == body["prep_groups"][0]["id"]
        assert body["ingredients"][0]["prep_method"] == "slice"


def test_legacy_recipe_without_prep_groups_still_works() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        ingredient = client.post("/api/ingredients", json={"name": f"Legacy Prep Ingredient {suffix}", "shopping_category_id": None, "preferred_unit_id": units["each"], "default_location_id": None, "perishable": False, "notes": None, "aliases": []}).json()
        response = client.post("/api/recipes", json={"name": f"Legacy Prep Recipe {suffix}", "description": None, "base_servings": "2", "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": None, "cook_time_minutes": None, "notes": None, "favorite": False, "meal_types": [], "tag_ids": [], "ingredients": [{"ingredient_id": ingredient["id"], "quantity": "1", "unit_id": units["each"], "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0}]})
        assert response.status_code == 201
        assert response.json()["prep_groups"] == []
        assert response.json()["ingredients"][0]["prep_group_id"] is None
