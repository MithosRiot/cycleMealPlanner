from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.session import engine
from app.main import app


def _cleanup(cycle_id: int | None, recipe_id: int | None, ingredient_id: int | None) -> None:
    """Remove every row created by this regression, even after an early assertion failure."""
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

        produced_lot_ids = [int(row[0]) for row in connection.execute(text(
            f"SELECT inventory_lot_id FROM leftovers WHERE completion_id IN ({completion_csv}) AND inventory_lot_id IS NOT NULL "
            f"UNION SELECT inventory_lot_id FROM meal_completion_outputs WHERE completion_id IN ({completion_csv}) AND inventory_lot_id IS NOT NULL"
        ))]
        ingredient_lot_ids: list[int] = []
        if ingredient_id is not None:
            ingredient_lot_ids = [int(row[0]) for row in connection.execute(
                text("SELECT id FROM inventory_lots WHERE ingredient_id=:ingredient_id"),
                {"ingredient_id": ingredient_id},
            )]
        lot_ids = sorted(set(produced_lot_ids + ingredient_lot_ids))
        lot_csv = ",".join(str(value) for value in lot_ids) or "-1"

        connection.execute(text(f"DELETE FROM meal_completion_allocations WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM meal_completion_outputs WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM leftovers WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM meal_completion_usage WHERE completion_id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM meal_completions WHERE id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM planned_cooking_timers WHERE planned_meal_id IN ({planned_csv})"))
        connection.execute(text(f"DELETE FROM gather_lot_selections WHERE planned_meal_id IN ({planned_csv})"))

        if cycle_id is not None:
            connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text(
                "DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle_id)"
            ), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle_id"), {"cycle_id": cycle_id})

        connection.execute(text(f"DELETE FROM inventory_transactions WHERE lot_id IN ({lot_csv})"))
        connection.execute(text(f"DELETE FROM inventory_lots WHERE id IN ({lot_csv})"))
        connection.execute(text(f"DELETE FROM planned_meals WHERE id IN ({planned_csv})"))

        if cycle_id is not None:
            connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle_id"), {"cycle_id": cycle_id})
            connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle_id"), {"cycle_id": cycle_id})
        if recipe_id is not None:
            connection.execute(text("DELETE FROM recipes WHERE id=:recipe_id"), {"recipe_id": recipe_id})
        if ingredient_id is not None:
            connection.execute(text("DELETE FROM ingredient_aliases WHERE ingredient_id=:ingredient_id"), {"ingredient_id": ingredient_id})
            connection.execute(text("DELETE FROM ingredients WHERE id=:ingredient_id"), {"ingredient_id": ingredient_id})


def test_direct_recipe_flows_through_planning_operations_completion_and_production() -> None:
    suffix = uuid4().hex[:8]
    cycle_id: int | None = None
    recipe_id: int | None = None
    ingredient_id: int | None = None
    try:
        with TestClient(app) as client:
            units = client.get("/api/reference/units").json()
            each = next(item for item in units if item["code"] == "each")
            refrigerator = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Refrigerator")

            ingredient = client.post("/api/ingredients", json={
                "name": f"Direct Recipe Ingredient {suffix}",
                "shopping_category_id": None,
                "preferred_unit_id": each["id"],
                "default_location_id": refrigerator["id"],
                "perishable": False,
                "notes": None,
                "aliases": [],
            }).json()
            ingredient_id = ingredient["id"]
            lot_response = client.post("/api/inventory", json={
                "ingredient_id": ingredient_id,
                "location_id": refrigerator["id"],
                "quantity": "8",
                "unit_id": each["id"],
                "purchase_date": None,
                "opened_date": None,
                "expiration_date": None,
                "frozen_date": None,
                "thawed_date": None,
                "notes": None,
                "transaction_type": "MANUAL_ADD",
            })
            assert lot_response.status_code == 201
            lot = lot_response.json()

            recipe_response = client.post("/api/recipes", json={
                "name": f"Direct Recipe {suffix}",
                "description": "Direct Recipe workflow regression",
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
                "advance_prep": [{
                    "task_type": "PREP",
                    "title": "Direct prep task",
                    "lead_time_minutes": 30,
                    "duration_minutes": 5,
                    "instructions": "Prepare directly.",
                    "reminder_enabled": False,
                    "reminder_offset_minutes": None,
                    "prep_group_key": None,
                    "sort_order": 0,
                }],
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
            recipe = recipe_response.json()
            recipe_id = recipe["id"]

            cooking_response = client.put(f"/api/recipes/{recipe_id}/cooking-steps", json=[{
                "title": "Cook direct Recipe",
                "instructions": "Cook it.",
                "prep_group_id": None,
                "sort_order": 0,
                "timers": [],
                "recipe_equipment_ids": [],
                "temperatures": [],
                "coordination_stage": 0,
                "parallel_capable": False,
                "depends_on_step_orders": [],
            }])
            assert cooking_response.status_code == 200

            cycle_response = client.post("/api/meal-cycles", json={
                "name": f"Direct Recipe Cycle {suffix}",
                "duration_days": 1,
                "start_date": "2026-09-10",
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
            })
            assert cycle_response.status_code == 201
            cycle = cycle_response.json()
            cycle_id = cycle["id"]
            slot = cycle["slots"][0]

            placed_response = client.post(
                f"/api/meal-cycles/{cycle_id}/slots/{slot['id']}/planned-recipe",
                json={"recipe_id": recipe_id, "planned_servings": "4", "planned_leftover_servings": "1"},
            )
            assert placed_response.status_code == 201
            planned = placed_response.json()
            assert planned["source_type"] == "DIRECT_RECIPE"
            assert planned["meal_id"] is None
            assert planned["source_recipe_id"] == recipe_id
            assert planned["snapshot_name"] == recipe["name"]
            scaled = __import__("json").loads(planned["scaled_components"])
            assert len(scaled) == 1
            assert scaled[0]["recipe_id"] == recipe_id
            assert Decimal(scaled[0]["requested_servings"]) == Decimal("5")
            assert Decimal(scaled[0]["ingredients"][0]["quantity"]) == Decimal("5")

            reservations = client.post(f"/api/meal-cycles/{cycle_id}/reservations/regenerate")
            assert reservations.status_code == 200
            reservation_body = reservations.json()
            assert reservation_body["active_count"] == 1
            assert reservation_body["reservations"][0]["planned_meal_id"] == planned["id"]
            assert Decimal(reservation_body["reservations"][0]["quantity"]) == Decimal("5")

            shopping = client.post(f"/api/shopping/{cycle_id}/regenerate")
            assert shopping.status_code == 200
            shopping_item = next(item for item in shopping.json()["items"] if item["ingredient_id"] == ingredient_id)
            assert Decimal(shopping_item["required_quantity"]) == Decimal("5")
            assert Decimal(shopping_item["generated_quantity"]) == Decimal("0")

            prep = client.get(f"/api/meal-cycles/{cycle_id}/prep-schedule")
            assert prep.status_code == 200
            prep_task = prep.json()["tasks"][0]
            assert prep_task["planned_meal_id"] == planned["id"]
            assert prep_task["meal_id"] is None
            assert prep_task["recipe_id"] == recipe_id
            assert prep_task["title"] == "Direct prep task"

            gather = client.get(f"/api/meal-cycles/{cycle_id}/gather")
            assert gather.status_code == 200
            requirement = gather.json()["requirements"][0]
            assert requirement["planned_meal_id"] == planned["id"]
            assert requirement["recipe_id"] == recipe_id
            assert Decimal(requirement["required_quantity"]) == Decimal("5")

            cooking = client.get(f"/api/meal-cycles/{cycle_id}/cooking-mode")
            assert cooking.status_code == 200
            cooking_meal = cooking.json()["meals"][0]
            assert cooking_meal["planned_meal_id"] == planned["id"]
            assert cooking_meal["meal_name"] == recipe["name"]
            assert cooking_meal["steps"][0]["title"] == "Cook direct Recipe"

            draft = client.post(f"/api/planned-meals/{planned['id']}/completion")
            assert draft.status_code == 200
            assert Decimal(draft.json()["usages"][0]["planned_quantity"]) == Decimal("5")
            finalized = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
            assert finalized.status_code == 200
            assert finalized.json()["completion"]["status"] == "FINALIZED"
            assert Decimal(client.get(f"/api/inventory/{lot['id']}").json()["quantity"]) == Decimal("3")

            preview = client.get(f"/api/planned-meals/{planned['id']}/completion/production-preview")
            assert preview.status_code == 200
            assert Decimal(preview.json()["default_leftover_servings"]) == Decimal("1")
            committed = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
                "actual_servings_produced": "5",
                "actual_servings_eaten": "4",
                "leftover_location_id": refrigerator["id"],
                "leftover_expiration_date": "2026-09-12",
                "leftover_notes": "Direct Recipe leftover",
                "outputs": [],
            })
            assert committed.status_code == 200
            leftover = committed.json()["leftover"]
            assert leftover["source_meal_id"] is None
            assert leftover["source_recipe_id"] == recipe_id
            assert Decimal(leftover["leftover_servings"]) == Decimal("1")

            options = client.get("/api/produced-source-options")
            assert options.status_code == 200
            direct_leftover = next(row for row in options.json() if row["source_type"] == "LEFTOVER" and row["source_origin_planned_meal_id"] == planned["id"])
            assert direct_leftover["source_meal_id"] is None
            assert Decimal(direct_leftover["available_quantity"]) == Decimal("1")
    finally:
        _cleanup(cycle_id, recipe_id, ingredient_id)
