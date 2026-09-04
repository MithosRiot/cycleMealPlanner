from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    return config


def test_0032_recovers_after_partial_sqlite_ddl(tmp_path) -> None:
    db_path = tmp_path / "partial-0032.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url = os.environ.get("CYCLE_MEAL_PLANNER_DATABASE_URL")
    previous_env = os.environ.get("CYCLE_MEAL_PLANNER_ENV")
    os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = database_url
    os.environ["CYCLE_MEAL_PLANNER_ENV"] = "migration-recovery-test"
    try:
        command.upgrade(_config(), "0031_meal_completion_finalization")
        engine = create_engine(database_url)
        with engine.begin() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0031_meal_completion_finalization"
            connection.execute(text("ALTER TABLE meal_completions ADD COLUMN actual_servings_produced NUMERIC(10, 3)"))

        # Simulate the exact failure mode seen on Windows/SQLite: DDL persisted,
        # but Alembic never advanced past 0031. Retrying head must resume safely.
        command.upgrade(_config(), "head")

        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0032_completion_leftovers_outputs"
            completion_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(meal_completions)"))}
            inventory_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(inventory_lots)"))}
            tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
            serving = connection.execute(text("SELECT code, unit_family FROM measurement_units WHERE code='serving'")) .one()

        assert {"actual_servings_produced", "actual_servings_eaten", "production_committed_at"}.issubset(completion_columns)
        assert {"source_type", "source_id", "source_name"}.issubset(inventory_columns)
        assert {"leftovers", "meal_completion_outputs"}.issubset(tables)
        assert serving.code == "serving" and serving.unit_family == "SERVING"
        engine.dispose()
    finally:
        if previous_url is None:
            os.environ.pop("CYCLE_MEAL_PLANNER_DATABASE_URL", None)
        else:
            os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = previous_url
        if previous_env is None:
            os.environ.pop("CYCLE_MEAL_PLANNER_ENV", None)
        else:
            os.environ["CYCLE_MEAL_PLANNER_ENV"] = previous_env
