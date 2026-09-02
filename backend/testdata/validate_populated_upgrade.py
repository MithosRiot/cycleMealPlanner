from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text


BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(__file__).with_name("migration-upgrade-test.db").resolve()


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    database_url = f"sqlite:///{DB_PATH.as_posix()}"
    os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = database_url
    os.environ["CYCLE_MEAL_PLANNER_ENV"] = "migration-upgrade-test"

    # Build exactly the schema a user would have before the staple migration,
    # then populate both an Ingredient FK relationship and a Meal Cycle slot.
    # Upgrading to head therefore validates the historical 0020 -> 0021 path
    # plus the new 0021 -> 0022 scheduling migration on populated SQLite.
    command.upgrade(alembic_config(), "0020_inventory_reservations")

    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO ingredients
            (id, household_id, name, normalized_name, perishable, active, notes)
            VALUES (9001, 1, 'Migration Test Ingredient', 'migration test ingredient', 0, 1, 'must survive upgrade')
        """))
        connection.execute(text("""
            INSERT INTO ingredient_aliases
            (id, ingredient_id, alias, normalized_alias)
            VALUES (9001, 9001, 'Migration Alias', 'migration alias')
        """))
        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status, start_date, notes,
             population_rules, smart_preferences)
            VALUES (9001, 1, 'Migration Cycle', 'migration cycle', 1, 'DRAFT', '2026-09-01',
                    'must survive upgrade', '{}', '{}')
        """))
        connection.execute(text("""
            INSERT INTO meal_slot_definitions
            (id, cycle_id, label, sort_order)
            VALUES (9001, 9001, 'Dinner', 0)
        """))
        connection.execute(text("""
            INSERT INTO cycle_slots
            (id, cycle_id, slot_definition_id, day_number, sort_order)
            VALUES (9001, 9001, 9001, 1, 0)
        """))

    command.upgrade(alembic_config(), "head")

    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        row = connection.execute(text("""
            SELECT name, staple_enabled, staple_minimum, staple_target, staple_unit_id
            FROM ingredients WHERE id=9001
        """)).one()
        alias_count = connection.execute(
            text("SELECT COUNT(*) FROM ingredient_aliases WHERE ingredient_id=9001")
        ).scalar_one()
        slot = connection.execute(text("""
            SELECT label, serving_time
            FROM meal_slot_definitions WHERE id=9001
        """)).one()
        cycle_slot_count = connection.execute(
            text("SELECT COUNT(*) FROM cycle_slots WHERE id=9001 AND slot_definition_id=9001")
        ).scalar_one()
        columns = {
            item[1] for item in connection.execute(text("PRAGMA table_info(meal_slot_definitions)"))
        }

    assert version == "0022_cycle_scheduling"
    assert row.name == "Migration Test Ingredient"
    assert bool(row.staple_enabled) is False
    assert row.staple_minimum is None
    assert row.staple_target is None
    assert row.staple_unit_id is None
    assert alias_count == 1
    assert "serving_time" in columns
    assert slot.label == "Dinner"
    assert slot.serving_time is None
    assert cycle_slot_count == 1

    engine.dispose()
    DB_PATH.unlink(missing_ok=True)
    print("Populated SQLite upgrade 0020 -> 0022 succeeded and preserved Ingredient/Cycle data.")


if __name__ == "__main__":
    main()
