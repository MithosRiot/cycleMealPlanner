from decimal import Decimal

from fastapi.testclient import TestClient

from app.engines.recipe_scaling import scale_quantity
from app.main import app


def _unit_map(client: TestClient) -> dict[str, int]:
    response = client.get("/api/reference/units")
    assert response.status_code == 200
    return {item["code"]: item["id"] for item in response.json()}


def _create_ingredient(client: TestClient, name: str, unit_id: int) -> int:
    response = client.post(
        "/api/ingredients",
        json={
            "name": name,
            "shopping_category_id": None,
            "preferred_unit_id": unit_id,
            "default_location_id": None,
            "perishable": False,
            "notes": None,
            "aliases": [],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_recipe_crud_search_filter_archive_and_scaling() -> None:
    with TestClient(app) as client:
        units = _unit_map(client)
        flour_id = _create_ingredient(client, "Recipe Flour", units["oz"])
        eggs_id = _create_ingredient(client, "Recipe Eggs", units["each"])
        salt_id = _create_ingredient(client, "Recipe Salt", units["tsp"])
        garnish_id = _create_ingredient(client, "Recipe Garnish", units["each"])

        tag = client.post("/api/tags", json={"name": "Weeknight", "category": "STYLE"})
        assert tag.status_code == 201
        tag_id = tag.json()["id"]

        created = client.post(
            "/api/recipes",
            json={
                "name": "Test Pancakes",
                "description": "Structured test recipe",
                "base_servings": "4",
                "serving_unit": "servings",
                "yield_quantity": None,
                "yield_unit_id": None,
                "prep_time_minutes": 10,
                "cook_time_minutes": 15,
                "notes": "Test notes",
                "favorite": True,
                "meal_types": ["breakfast", "BREAKFAST"],
                "tag_ids": [tag_id],
                "ingredients": [
                    {
                        "ingredient_id": flour_id,
                        "quantity": "8",
                        "unit_id": units["oz"],
                        "display_text": "8 oz flour",
                        "preparation": None,
                        "optional": False,
                        "scaling_mode": "LINEAR",
                        "required_state": "ANY",
                        "sort_order": 10,
                        "notes": None,
                    },
                    {
                        "ingredient_id": eggs_id,
                        "quantity": "2",
                        "unit_id": units["each"],
                        "display_text": None,
                        "preparation": "beaten",
                        "optional": False,
                        "scaling_mode": "ROUND_UP",
                        "required_state": "REFRIGERATED",
                        "sort_order": 20,
                        "notes": None,
                    },
                    {
                        "ingredient_id": salt_id,
                        "quantity": "1",
                        "unit_id": units["tsp"],
                        "display_text": None,
                        "preparation": None,
                        "optional": False,
                        "scaling_mode": "FIXED",
                        "required_state": "ANY",
                        "sort_order": 30,
                        "notes": None,
                    },
                    {
                        "ingredient_id": garnish_id,
                        "quantity": "1",
                        "unit_id": units["each"],
                        "display_text": None,
                        "preparation": None,
                        "optional": True,
                        "scaling_mode": "MANUAL",
                        "required_state": "ANY",
                        "sort_order": 40,
                        "notes": "Adjust to taste",
                    },
                ],
            },
        )
        assert created.status_code == 201
        recipe = created.json()
        recipe_id = recipe["id"]
        assert recipe["meal_types"] == ["BREAKFAST"]
        assert [item["scaling_mode"] for item in recipe["ingredients"]] == [
            "LINEAR",
            "ROUND_UP",
            "FIXED",
            "MANUAL",
        ]

        filtered = client.get(
            "/api/recipes",
            params={"search": "pancake", "meal_type": "breakfast", "tag_id": tag_id, "favorite": True},
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()] == [recipe_id]

        scaled = client.post(
            f"/api/recipes/{recipe_id}/scale",
            json={"requested_servings": "6", "unit_overrides": {}},
        )
        assert scaled.status_code == 200
        result = scaled.json()
        assert Decimal(result["scale_factor"]) == Decimal("1.5")
        quantities = {item["scaling_mode"]: Decimal(item["quantity"]) for item in result["ingredients"]}
        assert quantities["LINEAR"] == Decimal("12")
        assert quantities["ROUND_UP"] == Decimal("3")
        assert quantities["FIXED"] == Decimal("1")
        assert quantities["MANUAL"] == Decimal("1")
        manual = next(item for item in result["ingredients"] if item["scaling_mode"] == "MANUAL")
        assert manual["manual_review"] is True

        linear_item = next(item for item in recipe["ingredients"] if item["scaling_mode"] == "LINEAR")
        converted = client.post(
            f"/api/recipes/{recipe_id}/scale",
            json={
                "requested_servings": "8",
                "unit_overrides": {str(linear_item["id"]): "lb"},
            },
        )
        assert converted.status_code == 200
        converted_item = next(
            item for item in converted.json()["ingredients"] if item["recipe_ingredient_id"] == linear_item["id"]
        )
        assert Decimal(converted_item["quantity"]) == Decimal("1")
        assert converted_item["unit_code"] == "lb"

        unsafe = client.post(
            f"/api/recipes/{recipe_id}/scale",
            json={
                "requested_servings": "8",
                "unit_overrides": {str(linear_item["id"]): "cup"},
            },
        )
        assert unsafe.status_code == 400

        updated = client.put(
            f"/api/recipes/{recipe_id}",
            json={
                "name": "Test Pancakes Updated",
                "description": None,
                "base_servings": "4",
                "serving_unit": "servings",
                "yield_quantity": None,
                "yield_unit_id": None,
                "prep_time_minutes": 8,
                "cook_time_minutes": 12,
                "notes": None,
                "favorite": False,
                "meal_types": ["DINNER"],
                "tag_ids": [],
                "ingredients": [
                    {
                        "ingredient_id": flour_id,
                        "quantity": "8",
                        "unit_id": units["oz"],
                        "optional": False,
                        "scaling_mode": "LINEAR",
                        "required_state": "ANY",
                        "sort_order": 10,
                    }
                ],
                "active": True,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Test Pancakes Updated"
        assert updated.json()["meal_types"] == ["DINNER"]
        assert len(updated.json()["ingredients"]) == 1

        archived = client.delete(f"/api/recipes/{recipe_id}")
        assert archived.status_code == 204
        assert client.get("/api/recipes").json() == []
        inactive = client.get("/api/recipes", params={"include_inactive": True})
        assert [item["id"] for item in inactive.json()] == [recipe_id]


def test_scaling_engine_uses_decimal_rules() -> None:
    linear, manual = scale_quantity(Decimal("2.5"), Decimal("1.2"), "LINEAR")
    rounded, _ = scale_quantity(Decimal("1.1"), Decimal("1.2"), "ROUND_UP")
    fixed, _ = scale_quantity(Decimal("7.25"), Decimal("3"), "FIXED")
    manual_quantity, manual_review = scale_quantity(Decimal("4.5"), Decimal("2"), "MANUAL")

    assert linear == Decimal("3.00")
    assert manual is False
    assert rounded == Decimal("2")
    assert fixed == Decimal("7.25")
    assert manual_quantity == Decimal("4.5")
    assert manual_review is True
