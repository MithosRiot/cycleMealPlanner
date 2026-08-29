import json
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_recipe(client: TestClient, name: str, meal_type: str) -> int:
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
            "meal_types": [meal_type],
            "tag_ids": [],
            "ingredients": [{
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
            }],
        },
    )
    assert recipe.status_code == 201
    return recipe.json()["id"]


def _create_meal(client: TestClient, name: str, meal_type: str) -> int:
    recipe_id = _create_recipe(client, f"{name} Recipe", meal_type)
    meal = client.post(
        "/api/meals",
        json={
            "name": name,
            "description": f"Original {name}",
            "favorite": False,
            "meal_types": [meal_type],
            "tag_ids": [],
            "recipes": [{
                "recipe_id": recipe_id,
                "serving_multiplier": "1",
                "default_servings": "4",
                "sort_order": 0,
                "notes": None,
            }],
        },
    )
    assert meal.status_code == 201
    return meal.json()["id"]


def test_manual_move_lock_snapshot_servings_leftovers_and_random_fill() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        breakfast_id = _create_meal(client, f"Placement Breakfast {suffix}", "BREAKFAST")
        dinner_id = _create_meal(client, f"Placement Dinner {suffix}", "DINNER")

        cycle_response = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Placement Cycle {suffix}",
                "duration_days": 2,
                "start_date": None,
                "notes": None,
                "slot_definitions": [
                    {"label": "Breakfast", "sort_order": 0},
                    {"label": "Dinner", "sort_order": 1},
                    {"label": "Other", "sort_order": 2},
                ],
            },
        )
        assert cycle_response.status_code == 201
        cycle = cycle_response.json()
        cycle_id = cycle["id"]
        breakfast_slots = [slot for slot in cycle["slots"] if slot["sort_order"] == 0]
        dinner_slots = [slot for slot in cycle["slots"] if slot["sort_order"] == 1]
        other_slots = [slot for slot in cycle["slots"] if slot["sort_order"] == 2]

        assigned = client.post(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal",
            json={"meal_id": breakfast_id},
        )
        assert assigned.status_code == 201
        assigned_body = assigned.json()
        snapshot_name = assigned_body["snapshot_name"]
        assert Decimal(assigned_body["planned_servings"]) == Decimal("4")
        assert Decimal(assigned_body["planned_leftover_servings"]) == Decimal("0")
        initial_scaled = json.loads(assigned_body["scaled_components"])
        assert Decimal(initial_scaled[0]["requested_servings"]) == Decimal("4")
        assert Decimal(initial_scaled[0]["ingredients"][0]["quantity"]) == Decimal("1")

        component_id = json.loads(assigned_body["snapshot_components"])[0]["meal_recipe_id"]
        planned_update = client.put(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal/planning",
            json={
                "planned_servings": "5",
                "planned_leftover_servings": "1",
                "component_serving_overrides": {},
            },
        )
        assert planned_update.status_code == 200
        updated_plan = planned_update.json()
        assert Decimal(updated_plan["planned_servings"]) == Decimal("5")
        assert Decimal(updated_plan["planned_leftover_servings"]) == Decimal("1")
        scaled = json.loads(updated_plan["scaled_components"])
        assert Decimal(scaled[0]["requested_servings"]) == Decimal("6")
        assert Decimal(scaled[0]["ingredients"][0]["quantity"]) == Decimal("1.5")

        override_update = client.put(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal/planning",
            json={
                "planned_servings": "5",
                "planned_leftover_servings": "1",
                "component_serving_overrides": {str(component_id): "8"},
            },
        )
        assert override_update.status_code == 200
        overridden = override_update.json()
        scaled = json.loads(overridden["scaled_components"])
        assert Decimal(scaled[0]["requested_servings"]) == Decimal("8")
        assert Decimal(scaled[0]["ingredients"][0]["quantity"]) == Decimal("2")

        invalid_override = client.put(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal/planning",
            json={
                "planned_servings": "5",
                "planned_leftover_servings": "1",
                "component_serving_overrides": {"999999": "2"},
            },
        )
        assert invalid_override.status_code == 422

        source_meal = client.get(f"/api/meals/{breakfast_id}").json()
        updated = client.put(
            f"/api/meals/{breakfast_id}",
            json={
                "name": f"Changed Breakfast {suffix}",
                "description": "Changed after planning",
                "favorite": source_meal["favorite"],
                "meal_types": source_meal["meal_types"],
                "tag_ids": [tag["id"] for tag in source_meal["tags"]],
                "recipes": [{
                    "recipe_id": item["recipe_id"],
                    "serving_multiplier": item["serving_multiplier"],
                    "default_servings": item["default_servings"],
                    "sort_order": item["sort_order"],
                    "notes": item["notes"],
                } for item in source_meal["recipes"]],
                "active": True,
            },
        )
        assert updated.status_code == 200
        persisted = client.get(f"/api/meal-cycles/{cycle_id}").json()
        planned = next(slot["planned_meal"] for slot in persisted["slots"] if slot["id"] == breakfast_slots[0]["id"])
        assert planned["snapshot_name"] == snapshot_name
        assert Decimal(planned["planned_servings"]) == Decimal("5")
        assert Decimal(planned["planned_leftover_servings"]) == Decimal("1")
        assert json.loads(planned["component_serving_overrides"])[str(component_id)] == "8"

        locked = client.put(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal/lock",
            json={"locked": True},
        )
        assert locked.status_code == 200
        assert locked.json()["locked"] is True
        assert client.delete(f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal").status_code == 409

        random_fill = client.post(f"/api/meal-cycles/{cycle_id}/random-fill")
        assert random_fill.status_code == 200
        assert random_fill.json()["filled_count"] == 3
        filled_cycle = client.get(f"/api/meal-cycles/{cycle_id}").json()
        by_id = {slot["id"]: slot for slot in filled_cycle["slots"]}
        assert by_id[breakfast_slots[0]["id"]]["planned_meal"]["locked"] is True
        assert by_id[breakfast_slots[1]["id"]]["planned_meal"] is not None
        assert all(by_id[slot["id"]]["planned_meal"] is not None for slot in dinner_slots)
        assert all(by_id[slot["id"]]["planned_meal"] is None for slot in other_slots)

        unlock = client.put(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal/lock",
            json={"locked": False},
        )
        assert unlock.status_code == 200
        target = other_slots[0]["id"]
        moved = client.post(
            f"/api/meal-cycles/{cycle_id}/slots/{breakfast_slots[0]['id']}/planned-meal/move",
            json={"target_cycle_slot_id": target},
        )
        assert moved.status_code == 200
        assert moved.json()["cycle_slot_id"] == target
        assert Decimal(moved.json()["planned_servings"]) == Decimal("5")
        assert Decimal(moved.json()["planned_leftover_servings"]) == Decimal("1")

        removed = client.delete(f"/api/meal-cycles/{cycle_id}/slots/{target}/planned-meal")
        assert removed.status_code == 204
