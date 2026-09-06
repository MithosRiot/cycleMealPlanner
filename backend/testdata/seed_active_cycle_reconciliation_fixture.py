from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:
    from seed_test_db import configure_database

CYCLE_ID = 9401
CYCLE_NAME = "Active Revision Test Cycle"
SLOT_ONE_ID = 9401
SLOT_TWO_ID = 9402
PLANNED_ID = 9401
RECIPE_ID = 9401
RECIPE_INGREDIENT_ID = 9401
INGREDIENT_ID = 9401
INGREDIENT_NAME = "Revision Test Ingredient"
RECIPE_NAME = "Revision Test Recipe"


def _configure() -> None:
    configure_database()
    from app.database.migrations import run_migrations
    run_migrations()


def _cleanup(connection) -> None:
    purchase_lot_ids = [int(row[0]) for row in connection.execute(text("""
        SELECT sip.inventory_lot_id
        FROM shopping_item_purchases sip
        JOIN shopping_list_items sli ON sli.id=sip.shopping_list_item_id
        JOIN shopping_lists sl ON sl.id=sli.shopping_list_id
        WHERE sl.meal_cycle_id=:cycle
    """), {"cycle": CYCLE_ID})]
    completion_ids = [int(row[0]) for row in connection.execute(
        text("SELECT id FROM meal_completions WHERE planned_meal_id=:planned"), {"planned": PLANNED_ID}
    )]
    completion_csv = ",".join(str(value) for value in completion_ids) or "-1"
    lot_csv = ",".join(str(value) for value in purchase_lot_ids) or "-1"

    connection.execute(text(f"DELETE FROM meal_completion_allocations WHERE completion_id IN ({completion_csv})"))
    connection.execute(text(f"DELETE FROM meal_completion_outputs WHERE completion_id IN ({completion_csv})"))
    connection.execute(text(f"DELETE FROM leftovers WHERE completion_id IN ({completion_csv})"))
    connection.execute(text(f"DELETE FROM meal_completion_usage WHERE completion_id IN ({completion_csv})"))
    connection.execute(text(f"DELETE FROM meal_completions WHERE id IN ({completion_csv})"))
    connection.execute(text("DELETE FROM planned_cooking_timers WHERE planned_meal_id=:planned"), {"planned": PLANNED_ID})
    connection.execute(text("DELETE FROM gather_lot_selections WHERE planned_meal_id=:planned"), {"planned": PLANNED_ID})
    connection.execute(text("DELETE FROM planned_meal_revisions WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("""
        DELETE FROM shopping_item_purchases WHERE shopping_list_item_id IN
        (SELECT sli.id FROM shopping_list_items sli JOIN shopping_lists sl ON sl.id=sli.shopping_list_id WHERE sl.meal_cycle_id=:cycle)
    """), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text(f"DELETE FROM inventory_transactions WHERE lot_id IN ({lot_csv})"))
    connection.execute(text(f"DELETE FROM inventory_lots WHERE id IN ({lot_csv})"))
    connection.execute(text("DELETE FROM planned_meals WHERE id=:planned"), {"planned": PLANNED_ID})
    connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM recipe_ingredient_substitutions WHERE recipe_ingredient_id=:ri"), {"ri": RECIPE_INGREDIENT_ID})
    connection.execute(text("DELETE FROM recipe_ingredients WHERE id=:ri"), {"ri": RECIPE_INGREDIENT_ID})
    connection.execute(text("DELETE FROM recipe_meal_types WHERE recipe_id=:recipe"), {"recipe": RECIPE_ID})
    connection.execute(text("DELETE FROM recipes WHERE id=:recipe"), {"recipe": RECIPE_ID})
    connection.execute(text("DELETE FROM ingredient_aliases WHERE ingredient_id=:ingredient"), {"ingredient": INGREDIENT_ID})
    connection.execute(text("DELETE FROM ingredients WHERE id=:ingredient"), {"ingredient": INGREDIENT_ID})


def seed_fixture() -> None:
    _configure()
    from app.database.session import SessionLocal, engine
    from app.models.meal_cycle import CycleSlot, MealCycle
    from app.api.shopping import _regenerate
    from app.services.active_cycle_reconciliation import reconcile_active_cycle

    with engine.begin() as connection:
        _cleanup(connection)
        each_id = int(connection.execute(text("SELECT id FROM measurement_units WHERE code='each'")).scalar_one())
        refrigerator_id = int(connection.execute(text("SELECT id FROM inventory_locations WHERE name='Refrigerator' AND household_id=1")).scalar_one())
        connection.execute(text("""
            INSERT INTO ingredients
            (id, household_id, name, normalized_name, shopping_category_id, preferred_unit_id,
             default_location_id, perishable, active, notes)
            VALUES (:id,1,:name,'revision test ingredient',NULL,:unit,:location,0,1,
                    'Deterministic ingredient with no starting Inventory for active revision UAT')
        """), {"id": INGREDIENT_ID, "name": INGREDIENT_NAME, "unit": each_id, "location": refrigerator_id})
        connection.execute(text("""
            INSERT INTO recipes
            (id, household_id, name, normalized_name, description, base_servings, serving_unit,
             prep_time_minutes, cook_time_minutes, favorite, active)
            VALUES (:id,1,:name,'revision test recipe','Deterministic active revision UAT Recipe',4,'servings',5,10,0,1)
        """), {"id": RECIPE_ID, "name": RECIPE_NAME})
        connection.execute(text("INSERT INTO recipe_meal_types (recipe_id, meal_type) VALUES (:recipe,'DINNER')"), {"recipe": RECIPE_ID})
        connection.execute(text("""
            INSERT INTO recipe_ingredients
            (id, recipe_id, ingredient_id, quantity, unit_id, optional, scaling_mode, required_state, sort_order)
            VALUES (:id,:recipe,:ingredient,4,:unit,0,'LINEAR','ANY',0)
        """), {"id": RECIPE_INGREDIENT_ID, "recipe": RECIPE_ID, "ingredient": INGREDIENT_ID, "unit": each_id})
        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status, lifecycle_status,
             start_date, notes, population_rules, smart_preferences, activated_at)
            VALUES (:id,1,:name,'active revision test cycle',2,'DRAFT','ACTIVE',:today,
                    'Deterministic v1.0 active-cycle reconciliation manual test fixture','{}','{}',:now)
        """), {"id": CYCLE_ID, "name": CYCLE_NAME, "today": date.today(), "now": datetime.utcnow()})
        connection.execute(text("""
            INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order, serving_time)
            VALUES (9401,:cycle,'Dinner',0,'18:30:00')
        """), {"cycle": CYCLE_ID})
        connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (:id,:cycle,9401,1,0)"), {"id": SLOT_ONE_ID, "cycle": CYCLE_ID})
        connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (:id,:cycle,9401,2,0)"), {"id": SLOT_TWO_ID, "cycle": CYCLE_ID})

        snapshot_components = json.dumps([{
            "meal_recipe_id": -1,
            "recipe_id": RECIPE_ID,
            "serving_multiplier": "1",
            "default_servings": None,
            "sort_order": 0,
            "notes": "Direct Recipe occurrence",
        }])
        scaled_components = json.dumps([{
            "meal_recipe_id": -1,
            "recipe_id": RECIPE_ID,
            "base_servings": "4",
            "requested_servings": "4",
            "scale_factor": "1",
            "ingredients": [{
                "recipe_ingredient_id": RECIPE_INGREDIENT_ID,
                "ingredient_id": INGREDIENT_ID,
                "quantity": "4",
                "unit_id": each_id,
                "scaling_mode": "LINEAR",
                "manual_review": False,
            }],
        }])
        connection.execute(text("""
            INSERT INTO planned_meals
            (id, cycle_slot_id, meal_id, source_type, source_recipe_id, locked,
             planned_servings, planned_leftover_servings, component_serving_overrides,
             scaled_components, snapshot_name, snapshot_description, snapshot_meal_types, snapshot_components)
            VALUES (:id,:slot,NULL,'DIRECT_RECIPE',:recipe,0,4,0,'{}',:scaled,:name,
                    'Deterministic active revision UAT occurrence','["DINNER"]',:components)
        """), {"id": PLANNED_ID, "slot": SLOT_ONE_ID, "recipe": RECIPE_ID, "scaled": scaled_components, "name": RECIPE_NAME, "components": snapshot_components})

    with SessionLocal() as db:
        cycle = db.scalar(
            select(MealCycle)
            .where(MealCycle.id == CYCLE_ID)
            .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
        )
        _regenerate(db, cycle)
        reconcile_active_cycle(db, CYCLE_ID)
        db.commit()

    print(f"Active revision fixture ready: {CYCLE_NAME} (ID {CYCLE_ID})")
    print(f"Day 1 Dinner: {RECIPE_NAME}, 4 servings; Day 2 Dinner: empty")
    print(f"Shopping baseline: {INGREDIENT_NAME}, 4 each required / 4 each generated / plan delta 0")
    print("Cycle status: ACTIVE")


def mark_finalized() -> None:
    _configure()
    from app.database.session import engine
    now = datetime.utcnow()
    with engine.begin() as connection:
        planned = connection.execute(text("""
            SELECT snapshot_name, planned_servings, planned_leftover_servings, scaled_components
            FROM planned_meals WHERE id=:planned
        """), {"planned": PLANNED_ID}).mappings().first()
        if planned is None:
            raise RuntimeError("Run the fixture before --mark-finalized")
        status = connection.execute(text("SELECT lifecycle_status FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID}).scalar_one()
        if status != "ACTIVE":
            raise RuntimeError("Fixture cycle must be ACTIVE before --mark-finalized")
        fingerprint_source = {
            "planned_servings": str(planned["planned_servings"]),
            "planned_leftover_servings": str(planned["planned_leftover_servings"]),
            "component_serving_overrides": {},
            "scaled_components": json.loads(planned["scaled_components"]),
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        connection.execute(text("DELETE FROM meal_completion_allocations WHERE completion_id IN (SELECT id FROM meal_completions WHERE planned_meal_id=:planned)"), {"planned": PLANNED_ID})
        connection.execute(text("DELETE FROM meal_completion_usage WHERE completion_id IN (SELECT id FROM meal_completions WHERE planned_meal_id=:planned)"), {"planned": PLANNED_ID})
        connection.execute(text("DELETE FROM meal_completions WHERE planned_meal_id=:planned"), {"planned": PLANNED_ID})
        connection.execute(text("""
            INSERT INTO meal_completions
            (planned_meal_id, status, plan_fingerprint, snapshot_name, snapshot_planned_servings,
             snapshot_planned_leftover_servings, snapshot_scaled_components, created_at, updated_at,
             finalized_at, actual_servings_produced, actual_servings_eaten)
            VALUES (:planned,'FINALIZED',:fingerprint,:name,:servings,:leftovers,:scaled,:now,:now,:now,:servings,:servings)
        """), {
            "planned": PLANNED_ID, "fingerprint": fingerprint, "name": planned["snapshot_name"],
            "servings": planned["planned_servings"], "leftovers": planned["planned_leftover_servings"],
            "scaled": planned["scaled_components"], "now": now,
        })
    print(f"Planned occurrence {PLANNED_ID} marked FINALIZED for immutable-edit UAT")


def verify_fixture() -> None:
    _configure()
    from app.database.session import engine
    with engine.connect() as connection:
        cycle = connection.execute(text("SELECT lifecycle_status FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID}).scalar_one_or_none()
        placement = connection.execute(text("SELECT cycle_slot_id, planned_servings FROM planned_meals WHERE id=:planned"), {"planned": PLANNED_ID}).first()
        reservation = connection.execute(text("SELECT quantity, status FROM inventory_reservations WHERE cycle_id=:cycle ORDER BY id LIMIT 1"), {"cycle": CYCLE_ID}).first()
        shopping = connection.execute(text("""
            SELECT sli.required_quantity, sli.generated_quantity, sli.baseline_required_quantity,
                   sli.plan_delta_quantity, sli.purchased_excess_quantity, sli.status
            FROM shopping_list_items sli JOIN shopping_lists sl ON sl.id=sli.shopping_list_id
            WHERE sl.meal_cycle_id=:cycle AND sli.ingredient_id=:ingredient
        """), {"cycle": CYCLE_ID, "ingredient": INGREDIENT_ID}).first()
        purchases = connection.execute(text("""
            SELECT COUNT(*) FROM shopping_item_purchases sip
            JOIN shopping_list_items sli ON sli.id=sip.shopping_list_item_id
            JOIN shopping_lists sl ON sl.id=sli.shopping_list_id WHERE sl.meal_cycle_id=:cycle
        """), {"cycle": CYCLE_ID}).scalar_one()
        revisions = connection.execute(text("SELECT COUNT(*) FROM planned_meal_revisions WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID}).scalar_one()
        finalized = connection.execute(text("SELECT COUNT(*) FROM meal_completions WHERE planned_meal_id=:planned AND status='FINALIZED'"), {"planned": PLANNED_ID}).scalar_one()
    print(f"cycle={cycle}; placement={placement}; reservation={reservation}; shopping={shopping}; purchases={purchases}; revisions={revisions}; finalized={finalized}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the deterministic ACTIVE-cycle reconciliation UAT fixture.")
    parser.add_argument("--mark-finalized", action="store_true", help="Mark the fixture occurrence FINALIZED after seeding it.")
    parser.add_argument("--verify", action="store_true", help="Print current fixture reconciliation state.")
    args = parser.parse_args()
    if args.mark_finalized:
        mark_finalized()
    elif args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
