from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import text

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    from seed_test_db import configure_database

CYCLE_ID = 9101
SLOT_DEFINITION_ID = 9101
SLOT_ID = 9101
PLANNED_MEAL_ID = 9101
CYCLE_NAME = "Lifecycle Test Cycle"


def _configure() -> None:
    configure_database()
    from app.database.migrations import run_migrations

    run_migrations()


def _cleanup(connection) -> None:
    connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_completions WHERE planned_meal_id=:planned"), {"planned": PLANNED_MEAL_ID})
    connection.execute(text("DELETE FROM planned_meals WHERE id=:planned"), {"planned": PLANNED_MEAL_ID})
    connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID})


def seed_fixture() -> None:
    _configure()
    from app.database.session import engine

    with engine.begin() as connection:
        _cleanup(connection)
        sample = connection.execute(text("""
            SELECT meal_id, planned_servings, planned_leftover_servings,
                   component_serving_overrides, scaled_components, snapshot_name,
                   snapshot_description, snapshot_meal_types, snapshot_components
            FROM planned_meals WHERE id=1
        """)).mappings().first()
        if sample is None:
            raise RuntimeError("Seeded Planned Meal 1 was not found. Run seed_test_db.py --reset first.")

        start_date = connection.execute(text("SELECT date('now')")).scalar_one()
        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status,
             lifecycle_status, start_date, notes, population_rules, smart_preferences)
            VALUES
            (:id,1,:name,'lifecycle test cycle',1,'DRAFT','DRAFT',:start,
             'Deterministic v1.0 lifecycle manual test fixture','{}','{}')
        """), {"id": CYCLE_ID, "name": CYCLE_NAME, "start": start_date})
        connection.execute(text("""
            INSERT INTO meal_slot_definitions
            (id, cycle_id, label, sort_order, serving_time)
            VALUES (:id,:cycle,'Dinner',0,'18:30:00')
        """), {"id": SLOT_DEFINITION_ID, "cycle": CYCLE_ID})
        connection.execute(text("""
            INSERT INTO cycle_slots
            (id, cycle_id, slot_definition_id, day_number, sort_order)
            VALUES (:id,:cycle,:definition,1,0)
        """), {"id": SLOT_ID, "cycle": CYCLE_ID, "definition": SLOT_DEFINITION_ID})
        connection.execute(text("""
            INSERT INTO planned_meals
            (id, cycle_slot_id, meal_id, source_type, locked, planned_servings,
             planned_leftover_servings, component_serving_overrides, scaled_components,
             snapshot_name, snapshot_description, snapshot_meal_types, snapshot_components)
            VALUES
            (:id,:slot,:meal,'SAVED_MEAL',1,:servings,:leftovers,:overrides,:scaled,
             :name,:description,:meal_types,:components)
        """), {
            "id": PLANNED_MEAL_ID,
            "slot": SLOT_ID,
            "meal": sample["meal_id"],
            "servings": sample["planned_servings"],
            "leftovers": sample["planned_leftover_servings"],
            "overrides": sample["component_serving_overrides"],
            "scaled": sample["scaled_components"],
            "name": sample["snapshot_name"],
            "description": sample["snapshot_description"],
            "meal_types": sample["snapshot_meal_types"],
            "components": sample["snapshot_components"],
        })
        connection.execute(text("""
            INSERT INTO inventory_reservations
            (household_id, cycle_id, planned_meal_id, meal_recipe_id, recipe_id,
             recipe_ingredient_id, ingredient_id, quantity, unit_id, status)
            SELECT household_id, :cycle, :planned, meal_recipe_id, recipe_id,
                   recipe_ingredient_id, ingredient_id, quantity, unit_id, 'ACTIVE'
            FROM inventory_reservations
            WHERE cycle_id=1 AND planned_meal_id=1 AND status='ACTIVE'
        """), {"cycle": CYCLE_ID, "planned": PLANNED_MEAL_ID})

        reservation_count = connection.execute(text("""
            SELECT COUNT(*) FROM inventory_reservations
            WHERE cycle_id=:cycle AND status='ACTIVE'
        """), {"cycle": CYCLE_ID}).scalar_one()

    print(f"Lifecycle fixture ready: {CYCLE_NAME} (ID {CYCLE_ID})")
    print(f"Status: DRAFT; start date: {start_date}; Dinner: 18:30; planned Meal: {sample['snapshot_name']}")
    print(f"Active Ingredient reservations: {reservation_count}")


def mark_finalized() -> None:
    _configure()
    from app.database.session import engine

    with engine.begin() as connection:
        cycle = connection.execute(text("""
            SELECT lifecycle_status FROM meal_cycles WHERE id=:cycle
        """), {"cycle": CYCLE_ID}).scalar_one_or_none()
        if cycle is None:
            raise RuntimeError("Lifecycle fixture does not exist. Run this script without --mark-finalized first.")
        if cycle != "ACTIVE":
            raise RuntimeError(f"Lifecycle Test Cycle must be ACTIVE before marking its Meal finalized; current status is {cycle}.")
        now = datetime.utcnow()
        connection.execute(text("DELETE FROM meal_completions WHERE planned_meal_id=:planned"), {"planned": PLANNED_MEAL_ID})
        connection.execute(text("""
            INSERT INTO meal_completions
            (planned_meal_id, status, plan_fingerprint, snapshot_name,
             snapshot_planned_servings, snapshot_planned_leftover_servings,
             snapshot_scaled_components, created_at, updated_at, finalized_at)
            SELECT id, 'FINALIZED', :fingerprint, snapshot_name, planned_servings,
                   planned_leftover_servings, scaled_components, :now, :now, :now
            FROM planned_meals WHERE id=:planned
        """), {"planned": PLANNED_MEAL_ID, "fingerprint": "f" * 64, "now": now})

    print(f"Lifecycle fixture Planned Meal {PLANNED_MEAL_ID} is marked FINALIZED.")
    print("Return to Meal Plan -> Cycle schedule and click Complete cycle.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or advance the deterministic v1.0 Meal Cycle lifecycle fixture.")
    parser.add_argument("--mark-finalized", action="store_true", help="Mark the fixture Planned Meal finalized after the cycle has been activated.")
    args = parser.parse_args()
    if args.mark_finalized:
        mark_finalized()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
