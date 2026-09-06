from __future__ import annotations

import argparse
import json
from datetime import date

from sqlalchemy import text

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:
    from seed_test_db import configure_database

CYCLE_ID = 9301
CYCLE_NAME = "Non-food Occurrence Test Cycle"


def _configure() -> None:
    configure_database()
    from app.database.migrations import run_migrations
    run_migrations()


def _cleanup(connection) -> None:
    connection.execute(text("DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM production_coverage_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID})


def seed_fixture() -> None:
    _configure()
    from app.database.session import engine

    with engine.begin() as connection:
        _cleanup(connection)
        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status, lifecycle_status,
             start_date, notes, population_rules, smart_preferences)
            VALUES (:id,1,:name,'non-food occurrence test cycle',4,'DRAFT','DRAFT',:today,
                    'Deterministic v1.0 non-food occurrence manual test fixture','{}','{}')
        """), {"id": CYCLE_ID, "name": CYCLE_NAME, "today": date.today()})
        connection.execute(text("""
            INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order, serving_time)
            VALUES (9301,:cycle,'Dinner',0,'18:30:00')
        """), {"cycle": CYCLE_ID})
        for day in range(1, 5):
            connection.execute(text("""
                INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order)
                VALUES (:id,:cycle,9301,:day,0)
            """), {"id": 9300 + day, "cycle": CYCLE_ID, "day": day})

    print(f"Non-food fixture ready: {CYCLE_NAME} (ID {CYCLE_ID})")
    print("Targets: Day 1 Manual, Day 2 Eating Out, Day 3 Skipped, Day 4 saved Meal regression")
    print("Manual title: Family event; notes: Food handled elsewhere")
    print("Eating Out title: Local restaurant; notes: Dinner out")
    print("Skipped notes: Not eating dinner")
    print("Saved Meal regression: Chicken Dinner")


def verify_fixture() -> None:
    _configure()
    from app.database.session import engine

    with engine.connect() as connection:
        rows = list(connection.execute(text("""
            SELECT cs.day_number, pm.id, pm.source_type, pm.snapshot_name, pm.snapshot_description,
                   pm.scaled_components, mc.status
            FROM cycle_slots cs
            LEFT JOIN planned_meals pm ON pm.cycle_slot_id=cs.id
            JOIN meal_cycles mc ON mc.id=cs.cycle_id
            WHERE cs.cycle_id=:cycle
            ORDER BY cs.day_number
        """), {"cycle": CYCLE_ID}).mappings())
        reservations = connection.execute(text("SELECT COUNT(*) FROM inventory_reservations WHERE cycle_id=:cycle AND status='ACTIVE'"), {"cycle": CYCLE_ID}).scalar_one()
        shopping_rows = list(connection.execute(text("""
            SELECT sli.source_trace FROM shopping_list_items sli
            WHERE sli.shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)
        """), {"cycle": CYCLE_ID}).mappings())
        completion_rows = list(connection.execute(text("""
            SELECT pm.source_type, mc.status
            FROM planned_meals pm
            JOIN meal_completions mc ON mc.planned_meal_id=pm.id
            JOIN cycle_slots cs ON cs.id=pm.cycle_slot_id
            WHERE cs.cycle_id=:cycle
            ORDER BY cs.day_number
        """), {"cycle": CYCLE_ID}).mappings())

    for row in rows:
        print(f"Day {row['day_number']}: {row['source_type']} · {row['snapshot_name']} · {row['snapshot_description'] or ''}")
    non_food_ids = {row["id"] for row in rows if row["source_type"] in {"MANUAL", "EATING_OUT", "SKIPPED"}}
    direct_shopping = 0
    for item in shopping_rows:
        for trace in json.loads(item["source_trace"] or "[]"):
            if isinstance(trace, dict) and trace.get("planned_meal_id") in non_food_ids:
                direct_shopping += 1
    finalized_non_food = sum(1 for row in completion_rows if row["source_type"] in {"MANUAL", "EATING_OUT", "SKIPPED"} and row["status"] == "FINALIZED")
    print(f"Active Ingredient reservations: {reservations}")
    print(f"Non-food Shopping demand rows: {direct_shopping}")
    print(f"Auto-finalized non-food occurrences: {finalized_non_food}")
    if rows:
        print(f"Cycle status: {rows[0]['status']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify the deterministic non-food occurrence manual-test fixture.")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
