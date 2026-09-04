from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _recipe_payload(name: str, ingredient_id: int, unit_id: int) -> dict:
    return {
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
        "meal_types": ["COORD_TEST"],
        "tag_ids": [],
        "prep_groups": [],
        "advance_prep": [],
        "equipment": [],
        "ingredients": [{
            "ingredient_id": ingredient_id,
            "prep_group_key": None,
            "quantity": "1",
            "unit_id": unit_id,
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
    }


def _step(title: str, stage: int, parallel: bool, dependencies: list[int] | None = None) -> dict:
    return {
        "title": title,
        "instructions": None,
        "prep_group_id": None,
        "sort_order": 0,
        "timers": [],
        "recipe_equipment_ids": [],
        "temperatures": [],
        "coordination_stage": stage,
        "parallel_capable": parallel,
        "depends_on_step_orders": dependencies or [],
    }


def test_multi_component_steps_are_interleaved_by_ready_stage() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        unit = next(item for item in units if item["code"] == "each")
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Coord Ingredient {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": unit["id"],
            "default_location_id": location["id"],
            "perishable": False,
            "notes": None,
            "aliases": [],
        }).json()

        recipe_a = client.post("/api/recipes", json=_recipe_payload(f"Coord A {suffix}", ingredient["id"], unit["id"])).json()
        recipe_b = client.post("/api/recipes", json=_recipe_payload(f"Coord B {suffix}", ingredient["id"], unit["id"])).json()

        save_a = client.put(f"/api/recipes/{recipe_a['id']}/cooking-steps", json=[
            _step("A start", 0, True),
            _step("A finish", 2, False),
        ])
        save_b = client.put(f"/api/recipes/{recipe_b['id']}/cooking-steps", json=[
            _step("B start", 0, True),
            _step("B finish", 1, False),
        ])
        assert save_a.status_code == 200
        assert save_b.status_code == 200

        meal = client.post("/api/meals", json={
            "name": f"Coord Meal {suffix}",
            "description": None,
            "favorite": False,
            "meal_types": ["COORD_TEST"],
            "tag_ids": [],
            "recipes": [
                {"recipe_id": recipe_a["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None},
                {"recipe_id": recipe_b["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 1, "notes": None},
            ],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Coord Cycle {suffix}",
            "duration_days": 1,
            "start_date": "2026-09-05",
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        assert client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]}).status_code == 201

        cooking = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode")
        assert cooking.status_code == 200
        result = cooking.json()["meals"][0]
        assert result["coordinated"] is True
        assert [row["title"] for row in result["steps"]] == ["A start", "B start", "B finish", "A finish"]
        assert result["steps"][0]["parallel_group"] == result["steps"][1]["parallel_group"] == 1
        assert result["steps"][2]["parallel_group"] is None
        assert result["steps"][3]["parallel_group"] is None


def test_cooking_step_dependency_cycle_is_rejected() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        unit = next(item for item in client.get("/api/reference/units").json() if item["code"] == "each")
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Coord Cycle Ingredient {suffix}", "shopping_category_id": None,
            "preferred_unit_id": unit["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        recipe = client.post("/api/recipes", json=_recipe_payload(f"Cycle Recipe {suffix}", ingredient["id"], unit["id"])).json()
        response = client.put(f"/api/recipes/{recipe['id']}/cooking-steps", json=[
            _step("First", 0, False, [1]),
            _step("Second", 0, False),
        ])
        assert response.status_code == 422
        assert "dependency cycle" in response.json()["detail"].lower()
