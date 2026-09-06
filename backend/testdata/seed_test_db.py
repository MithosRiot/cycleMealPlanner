from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime

from sqlalchemy import text

try:
    from testdata import seed_test_db_base as _base
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    import seed_test_db_base as _base

TEST_DB = _base.TEST_DB
configure_database = _base.configure_database


def _has_existing_seed_data() -> bool:
    if not TEST_DB.exists():
        return False
    try:
        with sqlite3.connect(TEST_DB) as connection:
            table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingredients'").fetchone()
            if table is None:
                return False
            return connection.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0] > 0
    except sqlite3.DatabaseError:
        return False


def _clear_extended_seed_data_before_reset() -> None:
    """Clear newer child/history tables before the base seed reset.

    The base seed reset predates Gather, Cooking Mode, completion history,
    leftovers/RecipeOutputs, produced-stock coverage, active-cycle revision
    provenance, and append-only Shopping purchase history. A populated test DB
    therefore has child rows that must be removed before the base reset can
    delete planned_meals, Inventory lots/transactions, Recipes, and related
    parents. Keep foreign-key enforcement ON here so CI validates the deletion
    order instead of masking it.
    """
    if not TEST_DB.exists():
        return

    tables = [
        "planned_meal_revisions",
        "shopping_item_purchases",
        "production_coverage_reservations",
        "meal_completion_allocations",
        "meal_completion_outputs",
        "leftovers",
        "meal_completion_usage",
        "meal_completions",
        "planned_cooking_timers",
        "gather_lot_selections",
        "recipe_cooking_dependencies",
        "recipe_cooking_temperatures",
        "recipe_cooking_step_equipment",
        "recipe_cooking_timers",
        "recipe_cooking_coordination",
        "recipe_cooking_steps",
    ]

    with sqlite3.connect(TEST_DB) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        existing = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in tables:
            if table in existing:
                connection.execute(f'DELETE FROM "{table}"')
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Seed reset pre-clear left foreign key violations: {violations}")
        connection.commit()


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
              AND NOT EXISTS (SELECT 1 FROM inventory_transactions WHERE lot_id=17 AND note='Seeded Gather test lot')
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


def _seed_cooking_steps() -> None:
    from app.database.session import engine
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM recipe_cooking_steps WHERE recipe_id IN (1,2)"))
        connection.execute(text("""
            INSERT INTO recipe_cooking_steps
            (id, recipe_id, prep_group_id, title, instructions, sort_order)
            VALUES
            (1,1,1,'Cook chicken','Cook the chicken until browned and cooked through.',0),
            (2,1,101,'Cook rice','Add rice and cook until tender.',1),
            (3,1,NULL,'Finish and serve','Combine components, taste, and serve.',2),
            (4,2,2,'Brown beef','Brown the ground beef and break it into crumbles.',0)
        """))
        connection.execute(text("""
            INSERT INTO recipe_cooking_timers
            (id, cooking_step_id, label, duration_seconds, notes, sort_order)
            VALUES
            (1,1,'Chicken cook',600,'Check doneness before serving.',0),
            (2,2,'Rice simmer',900,'Keep covered while simmering.',0),
            (3,2,'Rice rest',300,'Rest off heat before fluffing.',1)
        """))
        connection.execute(text("""
            INSERT INTO recipe_cooking_step_equipment
            (id, cooking_step_id, recipe_equipment_id, sort_order)
            VALUES (1,1,1,0),(2,2,2,0)
        """))
        connection.execute(text("""
            INSERT INTO recipe_cooking_temperatures
            (id, cooking_step_id, label, value, unit, notes, sort_order)
            VALUES
            (1,1,'Internal',165,'F','Verify chicken reaches a safe internal temperature.',0),
            (2,2,'Simmer',212,'F','Bring liquid to a boil before reducing to a simmer.',0)
        """))
        connection.execute(text("""
            INSERT INTO recipe_cooking_coordination (cooking_step_id, stage, parallel_capable)
            VALUES (1,0,1),(2,1,1),(3,3,0),(4,0,1)
        """))
        connection.execute(text("INSERT INTO recipe_cooking_dependencies (cooking_step_id, depends_on_step_id) VALUES (3,2)"))


def _seed_completion_draft() -> None:
    from app.database.session import engine
    with engine.begin() as connection:
        planned = connection.execute(text("""
            SELECT id, snapshot_name, planned_servings, planned_leftover_servings,
                   component_serving_overrides, scaled_components
            FROM planned_meals WHERE id=1
        """)).mappings().first()
        if planned is None:
            return
        fingerprint_source = {
            "planned_servings": str(planned["planned_servings"]),
            "planned_leftover_servings": str(planned["planned_leftover_servings"]),
            "component_serving_overrides": json.loads(planned["component_serving_overrides"] or "{}"),
            "scaled_components": json.loads(planned["scaled_components"] or "[]"),
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        connection.execute(text("DELETE FROM meal_completions WHERE planned_meal_id=1"))
        connection.execute(text("""
            INSERT INTO meal_completions
            (id, planned_meal_id, status, plan_fingerprint, snapshot_name,
             snapshot_planned_servings, snapshot_planned_leftover_servings,
             snapshot_scaled_components, created_at, updated_at)
            VALUES (1,1,'DRAFT',:fingerprint,:name,:servings,:leftovers,:components,:now,:now)
        """), {
            "fingerprint": fingerprint, "name": planned["snapshot_name"],
            "servings": planned["planned_servings"], "leftovers": planned["planned_leftover_servings"],
            "components": planned["scaled_components"], "now": datetime.utcnow(),
        })
        usage_id = 1
        for component_index, component in enumerate(json.loads(planned["scaled_components"] or "[]")):
            recipe_id = int(component["recipe_id"])
            recipe_name = connection.execute(text("SELECT name FROM recipes WHERE id=:id"), {"id": recipe_id}).scalar_one()
            component_key = int(component.get("meal_recipe_id") or -(component_index + 1))
            for scaled in component.get("ingredients", []):
                recipe_ingredient_id = int(scaled["recipe_ingredient_id"])
                ingredient_id = int(scaled["ingredient_id"])
                unit_id = int(scaled["unit_id"])
                ingredient_name = connection.execute(text("SELECT name FROM ingredients WHERE id=:id"), {"id": ingredient_id}).scalar_one()
                unit_code = connection.execute(text("SELECT code FROM measurement_units WHERE id=:id"), {"id": unit_id}).scalar_one()
                prep = connection.execute(text("""
                    SELECT preparation, prep_method, prep_size, prep_state FROM recipe_ingredients WHERE id=:id
                """), {"id": recipe_ingredient_id}).mappings().first()
                connection.execute(text("""
                    INSERT INTO meal_completion_usage
                    (id, completion_id, component_key, recipe_id, recipe_name, recipe_ingredient_id,
                     planned_ingredient_id, planned_ingredient_name, planned_quantity, planned_unit_id, planned_unit_code,
                     actual_ingredient_id, actual_ingredient_name, actual_quantity, actual_unit_id, actual_unit_code,
                     preparation, prep_method, prep_size, prep_state, notes)
                    VALUES
                    (:id,1,:component_key,:recipe_id,:recipe_name,:recipe_ingredient_id,
                     :ingredient_id,:ingredient_name,:quantity,:unit_id,:unit_code,
                     :ingredient_id,:ingredient_name,:quantity,:unit_id,:unit_code,
                     :preparation,:prep_method,:prep_size,:prep_state,NULL)
                """), {
                    "id": usage_id, "component_key": component_key, "recipe_id": recipe_id,
                    "recipe_name": recipe_name, "recipe_ingredient_id": recipe_ingredient_id,
                    "ingredient_id": ingredient_id, "ingredient_name": ingredient_name,
                    "quantity": scaled["quantity"], "unit_id": unit_id, "unit_code": unit_code,
                    "preparation": prep["preparation"] if prep else None,
                    "prep_method": prep["prep_method"] if prep else None,
                    "prep_size": prep["prep_size"] if prep else None,
                    "prep_state": prep["prep_state"] if prep else None,
                })
                usage_id += 1


def _seed_default_coverage() -> None:
    from app.database.session import engine
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM production_coverage_reservations"))
        connection.execute(text("""
            INSERT INTO production_coverage_reservations
            (cycle_id, planned_meal_id, source_type, source_origin_planned_meal_id, source_record_id,
             source_recipe_output_id, requested_quantity, unit_id, reserved_quantity, shortage_quantity,
             lot_id, status, release_reason, released_at, created_at, updated_at)
            SELECT 1, 2, 'LEFTOVER', 1, NULL, NULL, 2.000000, 16, 2.000000, 0.000000,
                   NULL, 'ACTIVE', NULL, NULL, :now, :now
            WHERE EXISTS (SELECT 1 FROM planned_meals WHERE id=2 AND source_type='LEFTOVER')
        """), {"now": datetime.utcnow()})


def _seed_direct_recipe_examples() -> None:
    from app.database.session import engine
    with engine.begin() as connection:
        connection.execute(text("UPDATE planned_meals SET source_recipe_id=NULL WHERE source_type!='DIRECT_RECIPE'"))


def seed(reset: bool = False):
    """Create or refresh the complete deterministic test database.

    This public function is also the import contract used by backend/run_test.py.
    Keep the CLI and local launcher on the same full seed path so both include
    all extended fixtures layered on top of the original base seed.
    """
    configure_database()
    from app.database.migrations import run_migrations
    run_migrations()

    if reset and _has_existing_seed_data():
        _clear_extended_seed_data_before_reset()
    _base.seed(reset=reset)
    _seed_typed_prep_examples()
    _seed_gather_examples()
    _seed_cooking_steps()
    _seed_completion_draft()
    _seed_default_coverage()
    _seed_direct_recipe_examples()
    print(f"Seeded deterministic test database: {TEST_DB}")
    return TEST_DB


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset and seed the deterministic Cycle Meal Planner test database.")
    parser.add_argument("--reset", action="store_true", help="Delete existing seeded data before recreating it.")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
