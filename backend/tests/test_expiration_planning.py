from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _unit(client: TestClient, code: str) -> dict:
    return next(item for item in client.get("/api/reference/units").json() if item["code"] == code)


def _location(client: TestClient) -> dict:
    return next(item for item in client.get("/api/reference/inventory-locations").json() if item["active"])


def _create_meal(client: TestClient, name: str, ingredient_name: str, unit_code: str = "lb") -> tuple[int, int]:
    unit = _unit(client, unit_code)
    ingredient = client.post(
        "/api/ingredients",
        json={
            "name": ingredient_name,
            "shopping_category_id": None,
            "preferred_unit_id": unit["id"],
            "default_location_id": None,
            "perishable": True,
            "notes": None,
            "aliases": [],
        },
    )
    assert ingredient.status_code == 201
    ingredient_id = ingredient.json()["id"]

    recipe = client.post(
        "/api/recipes",
        json={
            "name": f"{name} Recipe",
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
            "ingredients": [{
                "ingredient_id": ingredient_id,
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

    meal = client.post(
        "/api/meals",
        json={
            "name": name,
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
        },
    )
    assert meal.status_code == 201
    return meal.json()["id"], ingredient_id


def _add_lot(client: TestClient, ingredient_id: int, quantity: str, unit_code: str, expiration_date: str) -> int:
    unit = _unit(client, unit_code)
    location = _location(client)
    response = client.post(
        "/api/inventory",
        json={
            "ingredient_id": ingredient_id,
            "location_id": location["id"],
            "quantity": quantity,
            "unit_id": unit["id"],
            "purchase_date": "2026-08-30",
            "opened_date": None,
            "expiration_date": expiration_date,
            "frozen_date": None,
            "thawed_date": None,
            "notes": "expiration planning test",
            "transaction_type": "PURCHASE",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_expiration_suggestions_use_dates_units_and_unlocked_reorder_targets() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        target_meal_id, target_ingredient_id = _create_meal(
            client,
            f"Expiration Target {suffix}",
            f"Expiration Chicken {suffix}",
        )
        filler_meal_id, _ = _create_meal(
            client,
            f"Expiration Filler {suffix}",
            f"Expiration Rice {suffix}",
        )

        usable_lot_id = _add_lot(client, target_ingredient_id, "16", "oz", "2026-09-04")
        _add_lot(client, target_ingredient_id, "16", "oz", "2026-09-02")
        _add_lot(client, target_ingredient_id, "10", "each", "2026-09-04")

        cycle_response = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Expiration Cycle {suffix}",
                "duration_days": 3,
                "start_date": "2026-09-01",
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
            },
        )
        assert cycle_response.status_code == 201
        cycle = cycle_response.json()
        slots = sorted(cycle["slots"], key=lambda item: item["day_number"])

        filler = client.post(
            f"/api/meal-cycles/{cycle['id']}/slots/{slots[1]['id']}/planned-meal",
            json={"meal_id": filler_meal_id},
        )
        assert filler.status_code == 201
        target = client.post(
            f"/api/meal-cycles/{cycle['id']}/slots/{slots[2]['id']}/planned-meal",
            json={"meal_id": target_meal_id},
        )
        assert target.status_code == 201

        response = client.get(f"/api/meal-cycles/{cycle['id']}/expiration-suggestions")
        assert response.status_code == 200
        body = response.json()
        target_suggestion = next(item for item in body["suggestions"] if item["meal_id"] == target_meal_id)

        assert target_suggestion["day_number"] == 3
        assert target_suggestion["planned_date"] == "2026-09-03"
        assert target_suggestion["urgency_days"] == 1
        assert target_suggestion["suggested_empty_day_numbers"] == [1]
        assert target_suggestion["suggested_swap_day_numbers"] == [2]
        assert target_suggestion["can_move_earlier"] is True
        assert target_suggestion["can_swap_earlier"] is True

        matches = target_suggestion["expiring_matches"]
        assert len(matches) == 1
        assert matches[0]["inventory_lot_id"] == usable_lot_id
        assert matches[0]["expiration_date"] == "2026-09-04"
        assert matches[0]["usable_quantity"] == "16.000000"
        assert matches[0]["unit_code"] == "oz"

        lock_response = client.put(
            f"/api/meal-cycles/{cycle['id']}/slots/{slots[1]['id']}/planned-meal/lock",
            json={"locked": True},
        )
        assert lock_response.status_code == 200

        locked_response = client.get(f"/api/meal-cycles/{cycle['id']}/expiration-suggestions")
        locked_target = next(item for item in locked_response.json()["suggestions"] if item["meal_id"] == target_meal_id)
        assert locked_target["suggested_swap_day_numbers"] == []
        assert locked_target["can_swap_earlier"] is False
        assert locked_target["suggested_empty_day_numbers"] == [1]


def test_expiration_suggestions_require_cycle_start_date() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle = client.post(
            "/api/meal-cycles",
            json={
                "name": f"Undated Expiration Cycle {suffix}",
                "duration_days": 2,
                "start_date": None,
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0}],
            },
        )
        assert cycle.status_code == 201

        response = client.get(f"/api/meal-cycles/{cycle.json()['id']}/expiration-suggestions")
        assert response.status_code == 409
        assert response.json()["detail"] == "Set a cycle start date to evaluate expiration timing"
