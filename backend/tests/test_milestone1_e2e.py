from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app


def test_milestone1_user_path_persists_across_restart() -> None:
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        each_unit = next(unit for unit in units if unit["code"] == "each")

        pantry = client.post(
            "/api/reference/inventory-locations",
            json={"name": "E2E Pantry", "location_type": "PANTRY", "sort_order": 900},
        )
        assert pantry.status_code == 201
        pantry_id = pantry.json()["id"]

        freezer = client.post(
            "/api/reference/inventory-locations",
            json={"name": "E2E Freezer", "location_type": "FREEZER", "sort_order": 910},
        )
        assert freezer.status_code == 201
        freezer_id = freezer.json()["id"]

        edited_location = client.put(
            f"/api/reference/inventory-locations/{pantry_id}",
            json={
                "name": "E2E Pantry Shelf",
                "parent_location_id": None,
                "location_type": "PANTRY",
                "sort_order": 900,
                "active": True,
            },
        )
        assert edited_location.status_code == 200

        ingredient = client.post(
            "/api/ingredients",
            json={
                "name": "E2E Tortilla",
                "shopping_category_id": None,
                "preferred_unit_id": each_unit["id"],
                "default_location_id": pantry_id,
                "perishable": False,
                "notes": "Milestone 1 validation ingredient",
                "aliases": ["E2E Wrap"],
            },
        )
        assert ingredient.status_code == 201
        ingredient_id = ingredient.json()["id"]

        tag = client.post("/api/tags", json={"name": "E2E Quick", "category": "CUSTOM"})
        assert tag.status_code == 201
        tag_id = tag.json()["id"]

        recipe = client.post(
            "/api/recipes",
            json={
                "name": "E2E Tortilla Plate",
                "description": "Milestone 1 end-to-end recipe",
                "base_servings": "2",
                "serving_unit": "servings",
                "yield_quantity": None,
                "yield_unit_id": None,
                "prep_time_minutes": 5,
                "cook_time_minutes": 0,
                "notes": None,
                "favorite": True,
                "meal_types": ["LUNCH"],
                "tag_ids": [tag_id],
                "ingredients": [
                    {
                        "ingredient_id": ingredient_id,
                        "quantity": "2",
                        "unit_id": each_unit["id"],
                        "display_text": None,
                        "preparation": "warmed",
                        "optional": False,
                        "scaling_mode": "LINEAR",
                        "required_state": "ANY",
                        "sort_order": 0,
                        "notes": None,
                    }
                ],
            },
        )
        assert recipe.status_code == 201
        recipe_id = recipe.json()["id"]

        scaled = client.post(
            f"/api/recipes/{recipe_id}/scale",
            json={"requested_servings": "5", "unit_overrides": {}},
        )
        assert scaled.status_code == 200
        assert Decimal(scaled.json()["scale_factor"]) == Decimal("2.5")
        assert Decimal(scaled.json()["ingredients"][0]["quantity"]) == Decimal("5")

        lot = client.post(
            "/api/inventory",
            json={
                "ingredient_id": ingredient_id,
                "location_id": pantry_id,
                "quantity": "12",
                "unit_id": each_unit["id"],
                "purchase_date": "2026-08-29",
                "opened_date": None,
                "expiration_date": "2026-09-15",
                "frozen_date": None,
                "thawed_date": None,
                "notes": "E2E purchase",
                "transaction_type": "PURCHASE",
            },
        )
        assert lot.status_code == 201
        lot_id = lot.json()["id"]

        removed = client.post(f"/api/inventory/{lot_id}/remove", json={"quantity": "2", "note": "Used for lunch"})
        assert removed.status_code == 200
        assert Decimal(removed.json()["quantity"]) == Decimal("10")

        moved = client.post(
            f"/api/inventory/{lot_id}/transfer",
            json={"to_location_id": freezer_id, "note": "Freeze extras"},
        )
        assert moved.status_code == 200
        assert moved.json()["location_id"] == freezer_id

        corrected = client.post(
            f"/api/inventory/{lot_id}/correct",
            json={"quantity": "9", "note": "Physical count"},
        )
        assert corrected.status_code == 200
        assert Decimal(corrected.json()["quantity"]) == Decimal("9")

        invalid_remove = client.post(
            f"/api/inventory/{lot_id}/remove",
            json={"quantity": "10", "note": "Should fail"},
        )
        assert invalid_remove.status_code == 409

    # A second lifespan disposes and reconnects the SQLAlchemy engine while
    # retaining the same SQLite data file, simulating an application restart.
    with TestClient(app) as client:
        persisted_locations = client.get("/api/reference/inventory-locations").json()
        assert any(item["id"] == pantry_id and item["name"] == "E2E Pantry Shelf" for item in persisted_locations)
        assert any(item["id"] == freezer_id for item in persisted_locations)

        alias_search = client.get("/api/ingredients", params={"search": "E2E Wrap"})
        assert alias_search.status_code == 200
        assert [item["id"] for item in alias_search.json()] == [ingredient_id]

        persisted_recipe = client.get(f"/api/recipes/{recipe_id}")
        assert persisted_recipe.status_code == 200
        recipe_payload = persisted_recipe.json()
        assert recipe_payload["name"] == "E2E Tortilla Plate"
        assert recipe_payload["favorite"] is True
        assert recipe_payload["meal_types"] == ["LUNCH"]
        assert [item["id"] for item in recipe_payload["tags"]] == [tag_id]
        assert recipe_payload["ingredients"][0]["ingredient_id"] == ingredient_id

        persisted_lot = client.get(f"/api/inventory/{lot_id}")
        assert persisted_lot.status_code == 200
        lot_payload = persisted_lot.json()
        assert Decimal(lot_payload["quantity"]) == Decimal("9")
        assert lot_payload["location_id"] == freezer_id
        assert lot_payload["expiration_date"] == "2026-09-15"
        assert [tx["transaction_type"] for tx in lot_payload["transactions"]] == [
            "PURCHASE",
            "MANUAL_REMOVE",
            "TRANSFER",
            "CORRECTION",
        ]
