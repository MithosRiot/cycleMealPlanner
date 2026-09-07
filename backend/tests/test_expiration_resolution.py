from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.services.dashboard_use_soon import use_soon_rows
from app.services.expiration_resolution import expiration_resolution_rows


def _unit(client: TestClient, code: str = "each") -> dict:
    return next(row for row in client.get("/api/reference/units").json() if row["code"] == code)


def _location(client: TestClient, kind: str) -> dict:
    return next(row for row in client.get("/api/reference/inventory-locations").json() if row["active"] and row["location_type"] == kind)


def _ingredient(client: TestClient, name: str, perishable: bool = True) -> int:
    unit = _unit(client)
    response = client.post("/api/ingredients", json={
        "name": name,
        "shopping_category_id": None,
        "preferred_unit_id": unit["id"],
        "default_location_id": _location(client, "REFRIGERATOR")["id"],
        "perishable": perishable,
        "notes": None,
        "aliases": [],
    })
    assert response.status_code == 201
    return response.json()["id"]


def _recipe(client: TestClient, name: str, ingredient_ids: list[int]) -> int:
    unit = _unit(client)
    response = client.post("/api/recipes", json={
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
        "ingredients": [{
            "ingredient_id": ingredient_id,
            "quantity": "1",
            "unit_id": unit["id"],
            "display_text": None,
            "preparation": None,
            "optional": False,
            "scaling_mode": "LINEAR",
            "required_state": "ANY",
            "sort_order": index,
            "notes": None,
        } for index, ingredient_id in enumerate(ingredient_ids)],
    })
    assert response.status_code == 201
    return response.json()["id"]


def _meal(client: TestClient, name: str, recipe_id: int) -> int:
    response = client.post("/api/meals", json={
        "name": name,
        "description": None,
        "favorite": False,
        "meal_types": ["DINNER"],
        "tag_ids": [],
        "recipes": [{
            "recipe_id": recipe_id,
            "serving_multiplier": "1",
            "default_servings": "4",
            "sort_order": 0,
            "notes": None,
        }],
    })
    assert response.status_code == 201
    return response.json()["id"]


def _lot(client: TestClient, ingredient_id: int, expiration: str) -> int:
    response = client.post("/api/inventory", json={
        "ingredient_id": ingredient_id,
        "location_id": _location(client, "REFRIGERATOR")["id"],
        "quantity": "5",
        "unit_id": _unit(client)["id"],
        "purchase_date": "2026-09-05",
        "opened_date": None,
        "expiration_date": expiration,
        "frozen_date": None,
        "thawed_date": None,
        "notes": "expiration resolution test",
        "transaction_type": "PURCHASE",
    })
    assert response.status_code == 201
    return response.json()["id"]


def _cycle(client: TestClient, name: str) -> dict:
    response = client.post("/api/meal-cycles", json={
        "name": name,
        "duration_days": 3,
        "start_date": "2026-09-06",
        "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00"}],
    })
    assert response.status_code == 201
    return response.json()


def test_resolution_ranking_prefers_multiple_expiring_items_and_explicit_no_suggestion() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        yogurt = _ingredient(client, f"Resolution Yogurt {suffix}")
        spinach = _ingredient(client, f"Resolution Spinach {suffix}")
        shelf = _ingredient(client, f"Resolution Shelf {suffix}", perishable=False)
        recovery_recipe = _recipe(client, f"Resolution Recovery Recipe {suffix}", [yogurt, spinach])
        _recipe(client, f"Resolution Yogurt Only {suffix}", [yogurt])
        recovery_meal = _meal(client, f"Resolution Recovery Meal {suffix}", recovery_recipe)
        yogurt_lot = _lot(client, yogurt, "2026-09-08")
        _lot(client, spinach, "2026-09-08")
        shelf_lot = _lot(client, shelf, "2026-09-08")
        cycle = _cycle(client, f"Resolution Cycle {suffix}")

        with SessionLocal() as db:
            body = expiration_resolution_rows(db, cycle["id"], today=date(2026, 9, 6))

        yogurt_row = next(row for row in body["resolutions"] if row["lot_id"] == yogurt_lot)
        assert yogurt_row["status"] == "ACTIONABLE"
        assert yogurt_row["actions"][0]["kind"] == "PLAN_MEAL"
        assert yogurt_row["actions"][0]["meal_id"] == recovery_meal
        assert yogurt_row["actions"][0]["matched_expiring_items"] == 2
        assert yogurt_row["actions"][0]["shopping_shortage_lines"] == 0
        assert any(action["kind"] == "FREEZE" for action in yogurt_row["actions"])

        shelf_row = next(row for row in body["resolutions"] if row["lot_id"] == shelf_lot)
        assert shelf_row["status"] == "NO_SUGGESTION"
        assert shelf_row["actions"] == []
        assert shelf_row["no_suggestion_reason"].startswith("No compatible Meal")


def test_freeze_resolution_marks_lot_frozen_moves_to_freezer_and_removes_use_soon() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        ingredient_id = _ingredient(client, f"Resolution Freeze {suffix}")
        lot_id = _lot(client, ingredient_id, "2026-09-08")
        freezer = _location(client, "FREEZER")

        response = client.post(f"/api/inventory/{lot_id}/freeze", json={
            "freezer_location_id": freezer["id"],
            "note": "freeze resolution test",
        })
        assert response.status_code == 200
        lot = response.json()
        assert lot["location_id"] == freezer["id"]
        assert lot["frozen_date"] is not None
        assert lot["thawed_date"] is None
        assert lot["expiration_date"] == "2026-09-08"

        detail = client.get(f"/api/inventory/{lot_id}").json()
        transfer = detail["transactions"][-1]
        assert transfer["transaction_type"] == "TRANSFER"
        assert transfer["to_location_id"] == freezer["id"]
        assert transfer["note"] == "freeze resolution test"

        with SessionLocal() as db:
            rows = use_soon_rows(db, horizon_days=7, today=date(2026, 9, 6))
        assert all(row["lot_id"] != lot_id for row in rows)
