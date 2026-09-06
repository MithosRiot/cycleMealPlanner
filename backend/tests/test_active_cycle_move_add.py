from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.session import engine
from app.main import app


def _cleanup(cycle_id: int | None, recipe_id: int | None, ingredient_id: int | None) -> None:
    if cycle_id is None:
        return
    with engine.begin() as connection:
        planned_ids = [int(row[0]) for row in connection.execute(text(
            "SELECT id FROM planned_meals WHERE cycle_slot_id IN (SELECT id FROM cycle_slots WHERE cycle_id=:cycle)"
        ), {"cycle": cycle_id})]
        planned_csv = ",".join(str(value) for value in planned_ids) or "-1"
        connection.execute(text(f"DELETE FROM planned_cooking_timers WHERE planned_meal_id IN ({planned_csv})"))
        connection.execute(text(f"DELETE FROM gather_lot_selections WHERE planned_meal_id IN ({planned_csv})"))
        connection.execute(text("DELETE FROM planned_meal_revisions WHERE cycle_id=:cycle"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM shopping_item_purchases WHERE shopping_list_item_id IN (SELECT sli.id FROM shopping_list_items sli JOIN shopping_lists sl ON sl.id=sli.shopping_list_id WHERE sl.meal_cycle_id=:cycle)"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle"), {"cycle": cycle_id})
        connection.execute(text(f"DELETE FROM planned_meals WHERE id IN ({planned_csv})"))
        connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle"), {"cycle": cycle_id})
        connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": cycle_id})
        if recipe_id is not None:
            connection.execute(text("DELETE FROM recipe_ingredients WHERE recipe_id=:recipe"), {"recipe": recipe_id})
            connection.execute(text("DELETE FROM recipe_meal_types WHERE recipe_id=:recipe"), {"recipe": recipe_id})
            connection.execute(text("DELETE FROM recipes WHERE id=:recipe"), {"recipe": recipe_id})
        if ingredient_id is not None:
            connection.execute(text("DELETE FROM ingredient_aliases WHERE ingredient_id=:ingredient"), {"ingredient": ingredient_id})
            connection.execute(text("DELETE FROM ingredients WHERE id=:ingredient"), {"ingredient": ingredient_id})


def test_active_move_then_add_reconciles_current_demand_and_revision_provenance() -> None:
    suffix = uuid4().hex[:8]
    cycle_id = recipe_id = ingredient_id = None
    try:
        with TestClient(app) as client:
            units = {item["code"]: item for item in client.get("/api/reference/units").json()}
            location = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Refrigerator")
            ingredient = client.post("/api/ingredients", json={
                "name": f"Active Move Ingredient {suffix}",
                "shopping_category_id": None,
                "preferred_unit_id": units["each"]["id"],
                "default_location_id": location["id"],
                "perishable": False,
                "notes": None,
                "aliases": [],
            })
            assert ingredient.status_code == 201
            ingredient_id = ingredient.json()["id"]
            recipe = client.post("/api/recipes", json={
                "name": f"Active Move Recipe {suffix}",
                "description": None,
                "base_servings": "4",
                "serving_unit": "servings",
                "yield_quantity": None,
                "yield_unit_id": None,
                "prep_time_minutes": 0,
                "cook_time_minutes": 0,
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
                    "unit_id": units["each"]["id"],
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
            assert recipe.status_code == 201
            recipe_id = recipe.json()["id"]
            cycle = client.post("/api/meal-cycles", json={
                "name": f"Active Move Cycle {suffix}",
                "duration_days": 2,
                "start_date": "2026-09-10",
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
            })
            assert cycle.status_code == 201
            cycle_data = cycle.json()
            cycle_id = cycle_data["id"]
            slots = sorted(cycle_data["slots"], key=lambda row: row["day_number"])

            for slot in slots:
                placed = client.post(
                    f"/api/meal-cycles/{cycle_id}/slots/{slot['id']}/planned-recipe",
                    json={"recipe_id": recipe_id, "planned_servings": "4", "planned_leftover_servings": "0"},
                )
                assert placed.status_code == 201
            assert client.post(f"/api/meal-cycles/{cycle_id}/reservations/regenerate").status_code == 200
            initial_shopping = client.post(f"/api/shopping/{cycle_id}/regenerate").json()
            initial_item = next(row for row in initial_shopping["items"] if row["ingredient_id"] == ingredient_id)
            assert Decimal(initial_item["required_quantity"]) == Decimal("8")
            assert Decimal(initial_item["baseline_required_quantity"]) == Decimal("8")
            assert client.post(f"/api/meal-cycles/{cycle_id}/activate").status_code == 200

            removed = client.delete(f"/api/meal-cycles/{cycle_id}/slots/{slots[1]['id']}/planned-meal")
            assert removed.status_code == 204
            after_remove = client.get(f"/api/shopping/{cycle_id}").json()
            item = next(row for row in after_remove["items"] if row["ingredient_id"] == ingredient_id)
            assert Decimal(item["required_quantity"]) == Decimal("4")
            assert Decimal(item["plan_delta_quantity"]) == Decimal("-4")

            source_cycle = client.get(f"/api/meal-cycles/{cycle_id}").json()
            source_planned = next(row["planned_meal"] for row in source_cycle["slots"] if row["id"] == slots[0]["id"])
            moved = client.post(
                f"/api/meal-cycles/{cycle_id}/slots/{slots[0]['id']}/planned-meal/move",
                json={"target_cycle_slot_id": slots[1]["id"]},
            )
            assert moved.status_code == 200
            assert moved.json()["id"] == source_planned["id"]
            assert moved.json()["cycle_slot_id"] == slots[1]["id"]
            after_move = client.get(f"/api/shopping/{cycle_id}").json()
            item = next(row for row in after_move["items"] if row["ingredient_id"] == ingredient_id)
            assert Decimal(item["required_quantity"]) == Decimal("4")
            assert Decimal(item["plan_delta_quantity"]) == Decimal("-4")

            added = client.post(
                f"/api/meal-cycles/{cycle_id}/slots/{slots[0]['id']}/planned-recipe",
                json={"recipe_id": recipe_id, "planned_servings": "4", "planned_leftover_servings": "0"},
            )
            assert added.status_code == 201
            reservations = client.get(f"/api/meal-cycles/{cycle_id}/reservations").json()["reservations"]
            active = [row for row in reservations if row["status"] == "ACTIVE" and row["ingredient_id"] == ingredient_id]
            assert len(active) == 2
            assert sum((Decimal(row["quantity"]) for row in active), Decimal("0")) == Decimal("8")
            after_add = client.get(f"/api/shopping/{cycle_id}").json()
            item = next(row for row in after_add["items"] if row["ingredient_id"] == ingredient_id)
            assert Decimal(item["required_quantity"]) == Decimal("8")
            assert Decimal(item["plan_delta_quantity"]) == Decimal("0")

            with engine.connect() as connection:
                actions = [row[0] for row in connection.execute(text(
                    "SELECT action FROM planned_meal_revisions WHERE cycle_id=:cycle ORDER BY id"
                ), {"cycle": cycle_id})]
            assert "REMOVED" in actions
            assert "MOVED" in actions
    finally:
        _cleanup(cycle_id, recipe_id, ingredient_id)
