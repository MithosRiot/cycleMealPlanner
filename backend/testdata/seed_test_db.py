from __future__ import annotations

import argparse
import sqlite3

from sqlalchemy import text

try:
    from testdata import seed_test_db_base as _base
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    import seed_test_db_base as _base

TEST_DB = _base.TEST_DB
configure_database = _base.configure_database


def _has_existing_seed_data() -> bool:
    """Match the base seeder's non-reset behavior without mutating an existing DB."""
    if not TEST_DB.exists():
        return False
    try:
        with sqlite3.connect(TEST_DB) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingredients'"
            ).fetchone()
            if table is None:
                return False
            return connection.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0] > 0
    except sqlite3.DatabaseError:
        return False


def _seed_typed_prep_examples() -> None:
    from app.database.session import engine

    with engine.begin() as connection:
        connection.execute(text("UPDATE recipe_advance_prep SET task_type='PREP', reminder_enabled=1, reminder_offset_minutes=15 WHERE id=1"))
        connection.execute(text("UPDATE recipe_advance_prep SET task_type='THAW', reminder_enabled=1, reminder_offset_minutes=60 WHERE id=2"))
        connection.execute(text("""
            INSERT OR IGNORE INTO recipe_advance_prep
            (id, recipe_id, prep_group_id, task_type, title, lead_time_minutes,
             duration_minutes, instructions, reminder_enabled, reminder_offset_minutes, sort_order)
            VALUES
            (3, 1, 1, 'MARINATE', 'Marinate chicken', 120, 10,
             'Season chicken and refrigerate until cooking.', 0, NULL, 1)
        """))
        connection.execute(text("UPDATE recipe_advance_prep SET reminder_enabled=0, reminder_offset_minutes=NULL WHERE id=3"))


def _seed_gather_examples() -> None:
    from app.database.session import engine

    with engine.begin() as connection:
        reservation_rows = connection.execute(text("""
            SELECT ingredient_id, recipe_ingredient_id
            FROM inventory_reservations
            WHERE planned_meal_id=1 AND meal_recipe_id=1 AND status='ACTIVE'
        """)).all()
        reservations = {int(row.ingredient_id): int(row.recipe_ingredient_id) for row in reservation_rows}
        if 1 not in reservations:
            return

        # A second Chicken Breast lot makes the seeded Gather example explicitly multi-lot.
        connection.execute(text("""
            INSERT OR IGNORE INTO inventory_lots
            (id, household_id, ingredient_id, location_id, quantity, unit_id, purchase_date,
             opened_date, expiration_date, frozen_date, thawed_date, notes)
            SELECT 17,1,1,3,1.000000,2,date('now'),NULL,date('now','+12 day'),NULL,NULL,
                   'Seeded second chicken lot for Gather testing'
        """))
        connection.execute(text("""
            INSERT INTO inventory_transactions
            (household_id, lot_id, transaction_type, quantity_delta, unit_id, to_location_id, note)
            SELECT 1,17,'PURCHASE',1.000000,2,3,'Seeded Gather test lot'
            WHERE EXISTS (SELECT 1 FROM inventory_lots WHERE id=17)
              AND NOT EXISTS (
                SELECT 1 FROM inventory_transactions WHERE lot_id=17 AND note='Seeded Gather test lot'
            )
        """))

        connection.execute(text("DELETE FROM gather_lot_selections WHERE planned_meal_id=1 AND meal_recipe_id=1"))
        connection.execute(text("""
            INSERT INTO gather_lot_selections
            (planned_meal_id, meal_recipe_id, recipe_id, recipe_ingredient_id, ingredient_id, lot_id, quantity, unit_id)
            VALUES
            (1,1,1,:chicken_ri,1,1,0.500000,2),
            (1,1,1,:chicken_ri,1,17,0.500000,2)
        """), {"chicken_ri": reservations[1]})
        if 6 in reservations:
            connection.execute(text("""
                INSERT INTO gather_lot_selections
                (planned_meal_id, meal_recipe_id, recipe_id, recipe_ingredient_id, ingredient_id, lot_id, quantity, unit_id)
                VALUES (1,1,1,:ri,6,6,2.000000,8)
            """), {"ri": reservations[6]})
        if 10 in reservations:
            connection.execute(text("""
                INSERT INTO gather_lot_selections
                (planned_meal_id, meal_recipe_id, recipe_id, recipe_ingredient_id, ingredient_id, lot_id, quantity, unit_id)
                VALUES (1,1,1,:ri,10,10,1.000000,14)
            """), {"ri": reservations[10]})


def seed(reset: bool = False):
    had_existing_data = not reset and _has_existing_seed_data()
    path = _base.seed(reset=reset)
    if had_existing_data:
        return path
    _seed_typed_prep_examples()
    _seed_gather_examples()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the reproducible Cycle Meal Planner test database")
    parser.add_argument("--reset", action="store_true", help="clear and reseed mutable test data")
    args = parser.parse_args()
    seed(reset=args.reset)
    print(TEST_DB)


if __name__ == "__main__":
    main()
