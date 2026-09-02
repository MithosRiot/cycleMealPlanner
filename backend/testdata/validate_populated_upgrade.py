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

    # Build exactly the schema a user would have before this feature.
    command.upgrade(alembic_config(), "0020_inventory_reservations")

    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # A child row referencing ingredients is enough to reproduce the SQLite
    # failure caused by batch table recreation under foreign-key enforcement.
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

    assert version == "0021_staple_stock_rules"
    assert row.name == "Migration Test Ingredient"
    assert bool(row.staple_enabled) is False
    assert row.staple_minimum is None
    assert row.staple_target is None
    assert row.staple_unit_id is None
    assert alias_count == 1

    engine.dispose()
    DB_PATH.unlink(missing_ok=True)
    print("Populated SQLite upgrade 0020 -> 0021 succeeded and preserved referenced Ingredient data.")


if __name__ == "__main__":
    main()
