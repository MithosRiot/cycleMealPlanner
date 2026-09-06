from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.session import engine
from app.main import app


def _cleanup(cycle_id: int | None, recipe_id: int | None, ingredient_id: int | None) -> None:
    if cycle_id is None and recipe_id is None and ingredient_id is None:
        return
    with engine.begin() as connection:
        planned_ids: list[int] = []
        if cycle_id is not None:
            planned_ids = [int(row[0]) for row in connection.execute(text(
                "SELECT id FROM planned_meals WHERE cycle_slot_id IN (SELECT id FROM cycle_slots WHERE cycle_id=:cycle_id)"
            ), {"cycle_id": cycle_id})]
        planned_csv = ",".join(str(value) for value in planned_ids) or "-1"
        completion_ids = [int(row[0]) for row in connection.execute(text(
            f"SELECT id FROM meal_completions WHERE planned_meal_id IN ({planned_csv})"
        ))]
        completion_csv = ",".join(str(value) for value in completion_ids) or "-1"

        connection.execute(text(f"DELETE FROM meal_completion_allocations WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM meal_completion_outputs WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM leftovers WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM meal_completion_usage WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM meal_completions WHERE id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM planned_cooking_timers WHERE planned_meal_id IN ({planned_csv})"))
        connection.execute(text(f"DELETE FROM gather_lot_selections WHERE planned_meal_id IN ({planned_csv})"))

        shopping_lot_ids: list[int] = []
        if cycle_id is not None:
            shopping_lot_ids = [int(row[0]) for row in connection.execute(text("""
                SELECT sip.inventory_lot_id
                FROM shopping_item_purchases sip
                JOIN shopping_list_items sli ON sli.id=sip.shopping_list_item_id
                JOIN shopping_lists sl ON sl.id=sli.shopping_list_id
                WHERE sl.meal_cycle_id=:cycle_id
            """), {"cycle_id": cycle_id})]
            connection.execute(text("DELETE FROM planned_meal_revisions WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text(
                "DELETE FROM shopping_item_purchases WHERE shopping_list_item_id IN "
                "(SELECT sli.id FROM shopping_list_items sli JOIN shopping_lists sl ON sl.id=sli.shopping_list_id WHERE sl.meal_cycle_id=:cycle_id)"
            ), {"cycle_id": cycle_id})
            connection.execute(text(
                "DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle_id)"
            ), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle_id"), {"cycle_id": cycle_id})

        lot_csv = ",".join(str(value) for value in shopping_lot_ids) or "-1"
        connection.execute(text(f"DELETE FROM inventory_transactions WHERE lot_id IN ({lot_csv})"))
        connection.execute(text(f"DELETE FROM inventory_lots WHERE id IN ({lot_csv})"))
        connection.execute(text(f"DELETE FROM planned_meals WHERE id IN ({planned_csv})"))
        if cycle_id is not None:
            connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle_id"), {"cycle_id": cycle_id})
        if recipe_id is not None:
            connection.execute(text("DELETE FROM recipe_ingredients WHERE recipe_id=:recipe_id"), {"recipe_id": recipe_id})
            connection.execute(text("DELETE FROM recipes WHERE id=:recipe_id"), {"recipe_id": recipe_id})
        if ingredient_id is not None:
            connection.execute(text("DELETE FROM ingredient_aliases WHERE ingredient_id=:ingredient_id"), {"ingredient_id": ingredient_id})
            connection.execute(text("DELETE FROM ingredients WHERE id=:ingredient_id"), {"ingredient_id": ingredient_id})


def _make_active_direct_recipe(client: TestClient, suffix: str) -> tuple[int, int, int, int, int, int]:
    units = client.get("/api/reference/units").json()
    each = next(item for item in units if item["code"] == "each")
    refrigerator = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Refrigerator")

    ingredient_response = client.post("/api/ingredients", json={
        "name": f"Active Revision Ingredient {suffix}",
        "shopping_category_id": None,
        "preferred_unit_id": each["id"],
        "default_location_id": refrigerator["id"],
        "perishable": False,
        "notes": None,
        "aliases": [],
    })
    assert ingredient_response.status_code == 201
    ingredient_id = ingredient_response.json()["id"]

    recipe_response = client.post("/api/recipes", json={
        "name": f"Active Revision Recipe {suffix}",
        "description": "Active revision regression",
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
        "prep_groups": [],
        "advance_prep": [],
        "equipment": [],
        "ingredients": [{
            "ingredient_id": ingredient_id,
            "prep_group_key": None,
            "quantity": "4",
            "unit_id": each["id"],
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
    })
    assert recipe_response.status_code == 201
    recipe_id = recipe_response.json()["id"]

    cycle_response = client.post("/api/meal-cycles", json={
        "name": f"Active Revision Cycle {suffix}",
        "duration_days": 1,
        "start_date": "2026-09-10",
        "notes": None,
        "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
    })
    assert cycle_response.status_code == 201
    cycle = cycle_response.json()
    cycle_id = cycle["id"]
    slot_id = cycle["slots"][0]["id"]

    placed = client.post(
        f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-recipe",
        json={"recipe_id": recipe_id, "planned_servings": "4", "planned_leftover_servings": "0"},
    )
    assert placed.status_code == 201
    planned_id = placed.json()["id"]
    assert client.post(f"/api/meal-cycles/{cycle_id}/reservations/regenerate").status_code == 200
    shopping = client.post(f"/api/shopping/{cycle_id}/regenerate")
    assert shopping.status_code == 200
    shopping_item = next(row for row in shopping.json()["items"] if row["ingredient_id"] == ingredient_id)
    assert Decimal(shopping_item["required_quantity"]) == Decimal("4")
    assert Decimal(shopping_item["baseline_required_quantity"]) == Decimal("4")
    assert Decimal(shopping_item["plan_delta_quantity"]) == Decimal("0")
    activated = client.post(f"/api/meal-cycles/{cycle_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"
    return cycle_id, slot_id, planned_id, recipe_id, ingredient_id, refrigerator["id"]


def test_active_quantity_change_reconciles_reservations_shopping_and_revision_history() -> None:
    suffix = uuid4().hex[:8]
    cycle_id = recipe_id = ingredient_id = None
    try:
        with TestClient(app) as client:
            cycle_id, slot_id, planned_id, recipe_id, ingredient_id, _ = _make_active_direct_recipe(client, suffix)
            changed = client.put(
                f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal/planning",
                json={"planned_servings": "8", "planned_leftover_servings": "0", "component_serving_overrides": {}},
            )
            assert changed.status_code == 200
            scaled = __import__("json").loads(changed.json()["scaled_components"])
            assert Decimal(scaled[0]["ingredients"][0]["quantity"]) == Decimal("8")

            reservations = client.get(f"/api/meal-cycles/{cycle_id}/reservations")
            assert reservations.status_code == 200
            active = [row for row in reservations.json()["reservations"] if row["status"] == "ACTIVE"]
            assert len(active) == 1
            assert Decimal(active[0]["quantity"]) == Decimal("8")

            shopping = client.get(f"/api/shopping/{cycle_id}")
            assert shopping.status_code == 200
            item = next(row for row in shopping.json()["items"] if row["ingredient_id"] == ingredient_id)
            assert Decimal(item["required_quantity"]) == Decimal("8")
            assert Decimal(item["plan_delta_quantity"]) == Decimal("4")
            assert item["status"] == "PENDING"

            with engine.connect() as connection:
                revision = connection.execute(text("""
                    SELECT action, planned_meal_id, planned_servings, scaled_components
                    FROM planned_meal_revisions WHERE cycle_id=:cycle_id ORDER BY id DESC LIMIT 1
                """), {"cycle_id": cycle_id}).one()
            assert revision.action == "QUANTITY_CHANGED"
            assert revision.planned_meal_id == planned_id
            assert Decimal(revision.planned_servings) == Decimal("4")
            old_scaled = __import__("json").loads(revision.scaled_components)
            assert Decimal(old_scaled[0]["ingredients"][0]["quantity"]) == Decimal("4")
    finally:
        _cleanup(cycle_id, recipe_id, ingredient_id)


def test_active_removed_demand_preserves_purchase_history_and_finalized_edit_rolls_back() -> None:
    suffix = uuid4().hex[:8]
    cycle_id = recipe_id = ingredient_id = None
    try:
        with TestClient(app) as client:
            cycle_id, slot_id, planned_id, recipe_id, ingredient_id, refrigerator_id = _make_active_direct_recipe(client, suffix)
            shopping = client.get(f"/api/shopping/{cycle_id}").json()
            item = next(row for row in shopping["items"] if row["ingredient_id"] == ingredient_id)
            purchased = client.post(f"/api/shopping/{cycle_id}/items/{item['id']}/complete", json={
                "actual_quantity": "4",
                "actual_unit_id": item["unit_id"],
                "storage_location_id": refrigerator_id,
                "purchase_date": "2026-09-06",
                "expiration_date": None,
                "notes": "immutable active-revision purchase",
            })
            assert purchased.status_code == 200
            purchased_item = next(row for row in purchased.json()["items"] if row["ingredient_id"] == ingredient_id)
            assert len(purchased_item["purchases"]) == 1
            purchase_lot_id = purchased_item["purchases"][0]["inventory_lot_id"]

            removed = client.delete(f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal")
            assert removed.status_code == 204
            after = client.get(f"/api/shopping/{cycle_id}").json()
            after_item = next(row for row in after["items"] if row["ingredient_id"] == ingredient_id)
            assert Decimal(after_item["required_quantity"]) == Decimal("0")
            assert Decimal(after_item["plan_delta_quantity"]) == Decimal("-4")
            assert Decimal(after_item["purchased_excess_quantity"]) == Decimal("4")
            assert len(after_item["purchases"]) == 1
            assert after_item["purchases"][0]["inventory_lot_id"] == purchase_lot_id
            assert after_item["purchases"][0]["purchase_notes"] == "immutable active-revision purchase"

            replacement = client.post(
                f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-recipe",
                json={"recipe_id": recipe_id, "planned_servings": "4", "planned_leftover_servings": "0"},
            )
            assert replacement.status_code == 201
            finalized_id = replacement.json()["id"]
            draft = client.post(f"/api/planned-meals/{finalized_id}/completion")
            assert draft.status_code == 200
            finalized = client.post(f"/api/planned-meals/{finalized_id}/completion/finalize")
            assert finalized.status_code == 200

            before_reservations = client.get(f"/api/meal-cycles/{cycle_id}/reservations").json()
            before_shopping = client.get(f"/api/shopping/{cycle_id}").json()
            blocked = client.put(
                f"/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-meal/planning",
                json={"planned_servings": "8", "planned_leftover_servings": "0", "component_serving_overrides": {}},
            )
            assert blocked.status_code == 409
            assert "finalized" in blocked.json()["detail"].lower()
            current = client.get(f"/api/meal-cycles/{cycle_id}").json()
            current_planned = next(slot["planned_meal"] for slot in current["slots"] if slot["id"] == slot_id)
            assert Decimal(current_planned["planned_servings"]) == Decimal("4")
            assert client.get(f"/api/meal-cycles/{cycle_id}/reservations").json() == before_reservations
            assert client.get(f"/api/shopping/{cycle_id}").json() == before_shopping
    finally:
        _cleanup(cycle_id, recipe_id, ingredient_id)
