from __future__ import annotations

import argparse
import json
from datetime import date

from sqlalchemy import text

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:
    from seed_test_db import configure_database

CYCLE_ID = 9201
DEFINITION_ID = 9201
SLOT_ID = 9201
CYCLE_NAME = "Direct Recipe Test Cycle"


def _configure() -> None:
    configure_database()
    from app.database.migrations import run_migrations
    run_migrations()


def _cleanup(connection) -> None:
    planned_ids = [row[0] for row in connection.execute(text("SELECT id FROM planned_meals WHERE cycle_slot_id IN (SELECT id FROM cycle_slots WHERE cycle_id=:cycle)"), {"cycle": CYCLE_ID})]
    if planned_ids:
        ids = ",".join(str(int(value)) for value in planned_ids)
        completion_ids = [row[0] for row in connection.execute(text(f"SELECT id FROM meal_completions WHERE planned_meal_id IN ({ids})"))]
        if completion_ids:
            completion_csv = ",".join(str(int(value)) for value in completion_ids)
            connection.execute(text(f"DELETE FROM meal_completion_allocations WHERE completion_id IN ({completion_csv})"))
            connection.execute(text(f"DELETE FROM meal_completion_outputs WHERE completion_id IN ({completion_csv})"))
            connection.execute(text(f"DELETE FROM leftovers WHERE completion_id IN ({completion_csv})"))
            connection.execute(text(f"DELETE FROM meal_completion_usage WHERE completion_id IN ({completion_csv})"))
            connection.execute(text(f"DELETE FROM meal_completions WHERE id IN ({completion_csv})"))
        connection.execute(text(f"DELETE FROM planned_cooking_timers WHERE planned_meal_id IN ({ids})"))
        connection.execute(text(f"DELETE FROM gather_lot_selections WHERE planned_meal_id IN ({ids})"))
    connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM planned_meals WHERE cycle_slot_id IN (SELECT id FROM cycle_slots WHERE cycle_id=:cycle)"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID})


def seed_fixture() -> None:
    _configure()
    from app.database.session import engine

    with engine.begin() as connection:
        _cleanup(connection)
        recipe = connection.execute(text("SELECT id, name, base_servings FROM recipes WHERE id=1")).mappings().first()
        if recipe is None:
            raise RuntimeError("Seeded Recipe 1 was not found. Run seed_test_db.py --reset first.")
        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status, lifecycle_status,
             start_date, notes, population_rules, smart_preferences)
            VALUES (:id,1,:name,'direct recipe test cycle',1,'DRAFT','DRAFT',:today,
                    'Deterministic v1.0 direct Recipe manual test fixture','{}','{}')
        """), {"id": CYCLE_ID, "name": CYCLE_NAME, "today": date.today()})
        connection.execute(text("""
            INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order, serving_time)
            VALUES (:id,:cycle,'Dinner',0,'18:30:00')
        """), {"id": DEFINITION_ID, "cycle": CYCLE_ID})
        connection.execute(text("""
            INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order)
            VALUES (:id,:cycle,:definition,1,0)
        """), {"id": SLOT_ID, "cycle": CYCLE_ID, "definition": DEFINITION_ID})

    print(f"Direct Recipe fixture ready: {CYCLE_NAME} (ID {CYCLE_ID})")
    print(f"Empty target: Day 1 · Dinner · Slot {SLOT_ID} · {date.today().isoformat()} 18:30")
    print(f"Use Recipe: {recipe['name']} (ID {recipe['id']}, base servings {recipe['base_servings']})")
    print("Manual placement values: Eat servings 4; Planned leftovers 1")


def verify_fixture() -> None:
    _configure()
    from app.database.session import engine

    with engine.connect() as connection:
        planned = connection.execute(text("""
            SELECT pm.id, pm.meal_id, pm.source_type, pm.source_recipe_id, pm.planned_servings,
                   pm.planned_leftover_servings, pm.snapshot_name, pm.scaled_components
            FROM planned_meals pm
            WHERE pm.cycle_slot_id=:slot
        """), {"slot": SLOT_ID}).mappings().first()
        if planned is None:
            raise RuntimeError("No placement exists in Direct Recipe Test Cycle. Place the Recipe in the UI first.")
        reservations = connection.execute(text("""
            SELECT COUNT(*) AS count FROM inventory_reservations
            WHERE cycle_id=:cycle AND status='ACTIVE'
        """), {"cycle": CYCLE_ID}).scalar_one()
        shopping = connection.execute(text("""
            SELECT COUNT(*) AS count FROM shopping_list_items
            WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)
        """), {"cycle": CYCLE_ID}).scalar_one()
        units = {row.id: row.code for row in connection.execute(text("SELECT id, code FROM measurement_units"))}
        ingredients = {row.id: row.name for row in connection.execute(text("SELECT id, name FROM ingredients"))}

    print(f"Placement: {planned['snapshot_name']} · {planned['source_type']} · Planned Meal {planned['id']}")
    print(f"Provenance: meal_id={planned['meal_id']} · source_recipe_id={planned['source_recipe_id']}")
    print(f"Servings: eat={planned['planned_servings']} · leftovers={planned['planned_leftover_servings']}")
    components = json.loads(planned["scaled_components"] or "[]")
    for component in components:
        for row in component.get("ingredients", []):
            print(f"Requirement: {ingredients.get(int(row['ingredient_id']), row['ingredient_id'])} · {row['quantity']} {units.get(int(row['unit_id']), row['unit_id'])}")
    print(f"Active Ingredient reservations: {reservations}")
    print(f"Generated Shopping rows: {shopping}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify the deterministic direct Recipe manual-test fixture.")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
