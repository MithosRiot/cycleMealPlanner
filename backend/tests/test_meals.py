from fastapi.testclient import TestClient

from app.main import app


def _create_recipe(client: TestClient, name: str) -> int:
    unit = next(item for item in client.get("/api/reference/units").json() if item["code"] == "each")
    ingredient = client.post(
        "/api/ingredients",
        json={
            "name": f"{name} Ingredient",
            "shopping_category_id": None,
            "preferred_unit_id": unit["id"],
            "default_location_id": None,
            "perishable": False,
            "notes": None,
            "aliases": [],
        },
    )
    assert ingredient.status_code == 201
    recipe = client.post(
        "/api/recipes",
        json={
            "name": name,
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
            "ingredients": [
                {
                    "ingredient_id": ingredient.json()["id"],
                    "quantity": "1",
                    "unit_id": unit["id"],
                    "display_text": None,
                    "preparation": None,
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
    return recipe.json()["id"]


def test_saved_meal_crud_search_filter_and_archive() -> None:
    with TestClient(app) as client:
        main_recipe_id = _create_recipe(client, "Meal Test Main")
        side_recipe_id = _create_recipe(client, "Meal Test Side")
        tag = client.post("/api/tags", json={"name": "Meal Test Family", "category": "STYLE"})
        assert tag.status_code == 201

        created = client.post(
            "/api/meals",
            json={
                "name": "Meal Test Dinner",
                "description": "Main plus side",
                "favorite": True,
                "meal_types": ["dinner", "DINNER"],
                "tag_ids": [tag.json()["id"]],
                "recipes": [
                    {
                        "recipe_id": main_recipe_id,
                        "serving_multiplier": "1",
                        "default_servings": "4",
                        "sort_order": 10,
                        "notes": "Main",
                    },
                    {
                        "recipe_id": side_recipe_id,
                        "serving_multiplier": "0.5",
                        "default_servings": None,
                        "sort_order": 20,
                        "notes": "Side",
                    },
                ],
            },
        )
        assert created.status_code == 201
        meal = created.json()
        meal_id = meal["id"]
        assert meal["meal_types"] == ["DINNER"]
        assert [item["recipe_id"] for item in meal["recipes"]] == [main_recipe_id, side_recipe_id]
        assert meal["recipes"][1]["serving_multiplier"] == "0.500"

        filtered = client.get(
            "/api/meals",
            params={
                "search": "test dinner",
                "meal_type": "dinner",
                "tag_id": tag.json()["id"],
                "favorite": True,
            },
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()] == [meal_id]

        updated = client.put(
            f"/api/meals/{meal_id}",
            json={
                "name": "Meal Test Dinner Updated",
                "description": None,
                "favorite": False,
                "meal_types": ["LUNCH"],
                "tag_ids": [],
                "recipes": [
                    {
                        "recipe_id": side_recipe_id,
                        "serving_multiplier": "1.25",
                        "default_servings": "5",
                        "sort_order": 0,
                        "notes": None,
                    }
                ],
                "active": True,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Meal Test Dinner Updated"
        assert updated.json()["meal_types"] == ["LUNCH"]
        assert len(updated.json()["recipes"]) == 1
        assert updated.json()["recipes"][0]["recipe_id"] == side_recipe_id

        archived = client.delete(f"/api/meals/{meal_id}")
        assert archived.status_code == 204
        active_ids = {item["id"] for item in client.get("/api/meals").json()}
        assert meal_id not in active_ids
        inactive = client.get("/api/meals", params={"include_inactive": True}).json()
        inactive_by_id = {item["id"]: item for item in inactive}
        assert inactive_by_id[meal_id]["active"] is False


def test_saved_meal_requires_active_recipe() -> None:
    with TestClient(app) as client:
        recipe_id = _create_recipe(client, "Meal Test Archived Recipe")
        assert client.delete(f"/api/recipes/{recipe_id}").status_code == 204
        response = client.post(
            "/api/meals",
            json={
                "name": "Meal Test Invalid",
                "description": None,
                "favorite": False,
                "meal_types": [],
                "tag_ids": [],
                "recipes": [{"recipe_id": recipe_id, "serving_multiplier": "1", "sort_order": 0}],
            },
        )
        assert response.status_code == 400
