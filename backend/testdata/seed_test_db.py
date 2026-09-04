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


def _clear_production_coverage_before_reset() -> None:
    if not TEST_DB.exists():
        return
    with sqlite3.connect(TEST_DB) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='production_coverage_reservations'"
        ).fetchone()
        if exists is not None:
            connection.execute("DELETE FROM production_coverage_reservations")
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


def _seed_leftover_coverage_example() -> None:
    from app.database.session import SessionLocal, engine
    from app.services.production_coverage import reconcile_production_coverage

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM planned_meals WHERE id=2"))
        connection.execute(text("""
            INSERT INTO planned_meals
            (id, cycle_slot_id, meal_id, source_type, source_origin_planned_meal_id,
             source_record_id, source_recipe_output_id, source_quantity, source_unit_id,
             locked, planned_servings, planned_leftover_servings, component_serving_overrides,
             scaled_components, snapshot_name, snapshot_description, snapshot_meal_types, snapshot_components)
            VALUES
            (2,6,1,'LEFTOVER',1,NULL,NULL,2.000000,16,0,2,0,'{}','[]',
             'Leftover: Chicken Dinner','Seeded future use of Chicken Dinner leftovers','["DINNER"]','[]')
        """))
    with SessionLocal() as db:
        reconcile_production_coverage(db)
        db.commit()


def seed(reset: bool = False):
    had_existing_data = not reset and _has_existing_seed_data()
    if reset:
        _clear_production_coverage_before_reset()
    path = _base.seed(reset=reset)
    if had_existing_data:
        return path
    _seed_typed_prep_examples()
    _seed_gather_examples()
    _seed_cooking_steps()
    _seed_completion_draft()
    _seed_leftover_coverage_example()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the reproducible Cycle Meal Planner test database")
    parser.add_argument("--reset", action="store_true", help="clear and reseed mutable test data")
    args = parser.parse_args()
    seed(reset=args.reset)
    print(TEST_DB)


if __name__ == "__main__":
    main()
