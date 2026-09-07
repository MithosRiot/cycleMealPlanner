from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


HEAD_REVISION = "0039_manual_shopping_items"


def _config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    return config


def test_0038_upgrades_populated_sqlite_with_fk_reference_and_stale_batch_table(tmp_path) -> None:
    db_path = tmp_path / "p38-populated-fk.db"
    url = f"sqlite:///{db_path.as_posix()}"
    old_url = os.environ.get("CYCLE_MEAL_PLANNER_DATABASE_URL")
    old_env = os.environ.get("CYCLE_MEAL_PLANNER_ENV")
    os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = url
    os.environ["CYCLE_MEAL_PLANNER_ENV"] = "migration-recovery-test"

    try:
        command.upgrade(_config(), "0037_shopping_partial_substitutions")
        engine = create_engine(url)
        with engine.begin() as connection:
            unit_id = connection.execute(text("SELECT id FROM measurement_units ORDER BY id LIMIT 1")).scalar_one()
            location_id = connection.execute(text("SELECT id FROM inventory_locations ORDER BY id LIMIT 1")).scalar_one()
            connection.execute(text("INSERT INTO ingredients (id,household_id,name,normalized_name,perishable,active) VALUES (9910,1,'0038 FK Ingredient','0038 fk ingredient',0,1)"))
            connection.execute(text("INSERT INTO inventory_lots (id,household_id,ingredient_id,location_id,quantity,unit_id) VALUES (9910,1,9910,:location_id,5,:unit_id)"), {"location_id": location_id, "unit_id": unit_id})
            connection.execute(text("INSERT INTO inventory_transactions (id,household_id,lot_id,transaction_type,quantity_delta,unit_id,to_location_id) VALUES (9910,1,9910,'MANUAL_ADD',5,:unit_id,:location_id)"), {"unit_id": unit_id, "location_id": location_id})
            connection.execute(text("CREATE TABLE migration_tx_ref (id INTEGER PRIMARY KEY, tx_id INTEGER NOT NULL REFERENCES inventory_transactions(id) ON DELETE RESTRICT)"))
            connection.execute(text("INSERT INTO migration_tx_ref (id,tx_id) VALUES (1,9910)"))
            connection.execute(text("ALTER TABLE inventory_transactions ADD COLUMN reason VARCHAR(160)"))
            connection.execute(text("CREATE TABLE _alembic_tmp_inventory_transactions AS SELECT * FROM inventory_transactions WHERE 0"))
        engine.dispose()

        # Importing the application session module installs the same global
        # SQLite connect hook used by the real test app, including FK=ON.
        import app.database.session  # noqa: F401

        command.upgrade(_config(), "head")

        verify = create_engine(url)
        with verify.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD_REVISION
            assert connection.execute(text("SELECT tx_id FROM migration_tx_ref WHERE id=1")).scalar_one() == 9910
            assert connection.execute(text("SELECT COUNT(*) FROM inventory_transactions WHERE id=9910")).scalar_one() == 1
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
            tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
            assert "_alembic_tmp_inventory_transactions" not in tables
            assert "manual_shopping_items" in tables
            transaction_sql = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='inventory_transactions'" )).scalar_one()
            assert "WASTE" in transaction_sql and "SPOILAGE" in transaction_sql
        verify.dispose()
    finally:
        if old_url is None:
            os.environ.pop("CYCLE_MEAL_PLANNER_DATABASE_URL", None)
        else:
            os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = old_url
        if old_env is None:
            os.environ.pop("CYCLE_MEAL_PLANNER_ENV", None)
        else:
            os.environ["CYCLE_MEAL_PLANNER_ENV"] = old_env
