from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text


def _config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    return config


def _set_env(database_url: str) -> tuple[str | None, str | None]:
    previous_url = os.environ.get("CYCLE_MEAL_PLANNER_DATABASE_URL")
    previous_env = os.environ.get("CYCLE_MEAL_PLANNER_ENV")
    os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = database_url
    os.environ["CYCLE_MEAL_PLANNER_ENV"] = "migration-recovery-test"
    return previous_url, previous_env


def _restore_env(previous_url: str | None, previous_env: str | None) -> None:
    if previous_url is None:
        os.environ.pop("CYCLE_MEAL_PLANNER_DATABASE_URL", None)
    else:
        os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = previous_url
    if previous_env is None:
        os.environ.pop("CYCLE_MEAL_PLANNER_ENV", None)
    else:
        os.environ["CYCLE_MEAL_PLANNER_ENV"] = previous_env


def _engine(database_url: str):
    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def _seed_dependent_inventory(engine) -> tuple[int, int]:
    with engine.begin() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        unit_id = connection.execute(text("SELECT id FROM measurement_units ORDER BY id LIMIT 1")).scalar_one()
        location_id = connection.execute(text("SELECT id FROM inventory_locations ORDER BY id LIMIT 1")).scalar_one()
        connection.execute(text(
            "INSERT INTO ingredients (id, household_id, name, normalized_name, perishable, active, notes) "
            "VALUES (9901,1,'Migration Recovery Ingredient','migration recovery ingredient',0,1,NULL)"
        ))
        connection.execute(text(
            "INSERT INTO inventory_lots "
            "(id, household_id, ingredient_id, location_id, quantity, unit_id, notes) "
            "VALUES (9901,1,9901,:location_id,5,:unit_id,'must survive 0032 recovery')"
        ), {"location_id": location_id, "unit_id": unit_id})
        connection.execute(text(
            "INSERT INTO inventory_transactions "
            "(id, household_id, lot_id, transaction_type, quantity_delta, unit_id, to_location_id, note) "
            "VALUES (9901,1,9901,'MANUAL_ADD',5,:unit_id,:location_id,'dependent transaction must survive')"
        ), {"unit_id": unit_id, "location_id": location_id})
    return unit_id, location_id


def _seed_dependent_planning(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO meals (id, household_id, name, normalized_name, favorite, active) VALUES (9902,1,'Migration Meal','migration meal',0,1)"))
        connection.execute(text("INSERT INTO meal_cycles (id, household_id, name, normalized_name, duration_days, status, lifecycle_status, start_date, population_rules, smart_preferences) VALUES (9902,1,'Migration Direct Cycle','migration direct cycle',1,'DRAFT','DRAFT','2026-09-05','{}','{}')"))
        connection.execute(text("INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order, serving_time) VALUES (9902,9902,'Dinner',0,'18:00:00')"))
        connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (9902,9902,9902,1,0)"))
        connection.execute(text("""
            INSERT INTO planned_meals
            (id, cycle_slot_id, meal_id, source_type, locked, planned_servings, planned_leftover_servings,
             component_serving_overrides, scaled_components, snapshot_name, snapshot_meal_types, snapshot_components)
            VALUES (9902,9902,9902,'SAVED_MEAL',0,4,1,'{}','[]','Migration Meal','[]','[]')
        """))
        connection.execute(text("""
            INSERT INTO meal_completions
            (id, planned_meal_id, status, plan_fingerprint, snapshot_name, snapshot_planned_servings,
             snapshot_planned_leftover_servings, snapshot_scaled_components, created_at, updated_at)
            VALUES (9902,9902,'DRAFT',:fingerprint,'Migration Meal',4,1,'[]','2026-09-05 12:00:00','2026-09-05 12:00:00')
        """), {"fingerprint": "a" * 64})
        connection.execute(text("""
            INSERT INTO leftovers
            (id, completion_id, planned_meal_id, source_meal_id, source_meal_name, source_components,
             actual_servings_produced, actual_servings_eaten, leftover_servings, serving_unit, status, created_at)
            VALUES (9902,9902,9902,9902,'Migration Meal','[]',5,4,1,'serving','AVAILABLE','2026-09-05 12:00:00')
        """))


def _assert_recovered(engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0035_direct_recipe_occurrences"
        completion_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(meal_completions)"))}
        inventory_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(inventory_lots)"))}
        planned_info = {row[1]: row for row in connection.execute(text("PRAGMA table_info(planned_meals)"))}
        leftover_info = {row[1]: row for row in connection.execute(text("PRAGMA table_info(leftovers)"))}
        coverage_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(production_coverage_reservations)"))}
        cycle_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(meal_cycles)"))}
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        serving = connection.execute(text("SELECT code, unit_family FROM measurement_units WHERE code='serving'")) .one()
        fk_violations = connection.execute(text("PRAGMA foreign_key_check")).all()
        lot = connection.execute(text("SELECT ingredient_id, quantity, source_type FROM inventory_lots WHERE id=9901")).one()
        transaction = connection.execute(text("SELECT lot_id, transaction_type, quantity_delta FROM inventory_transactions WHERE id=9901")).one()

    assert {"actual_servings_produced", "actual_servings_eaten", "production_committed_at"}.issubset(completion_columns)
    assert {"source_type", "source_id", "source_name"}.issubset(inventory_columns)
    assert {"source_type", "source_recipe_id", "source_origin_planned_meal_id", "source_record_id", "source_recipe_output_id", "source_quantity", "source_unit_id"}.issubset(planned_info)
    assert "source_recipe_id" in leftover_info
    assert planned_info["meal_id"][3] == 0
    assert leftover_info["source_meal_id"][3] == 0
    assert {"source_origin_planned_meal_id", "requested_quantity", "reserved_quantity", "shortage_quantity", "status"}.issubset(coverage_columns)
    assert {"lifecycle_status", "activated_at", "completed_at", "cancelled_at"}.issubset(cycle_columns)
    assert {"leftovers", "meal_completion_outputs", "production_coverage_reservations"}.issubset(tables)
    assert "_alembic_tmp_inventory_lots" not in tables
    assert "_alembic_tmp_inventory_transactions" not in tables
    assert "_alembic_tmp_planned_meals" not in tables
    assert "_alembic_tmp_leftovers" not in tables
    assert serving.code == "serving" and serving.unit_family == "SERVING"
    assert fk_violations == []
    assert lot.ingredient_id == 9901 and lot.source_type == "INGREDIENT"
    assert transaction.lot_id == 9901 and transaction.transaction_type == "MANUAL_ADD"


def test_0032_recovers_after_partial_sqlite_ddl_with_foreign_keys_and_dependent_rows(tmp_path) -> None:
    db_path = tmp_path / "partial-0032.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url, previous_env = _set_env(database_url)
    try:
        command.upgrade(_config(), "0031_meal_completion_finalization")
        engine = _engine(database_url)
        _seed_dependent_inventory(engine)
        with engine.begin() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0031_meal_completion_finalization"
            connection.execute(text("ALTER TABLE meal_completions ADD COLUMN actual_servings_produced NUMERIC(10, 3)"))
        command.upgrade(_config(), "head")
        _assert_recovered(engine)
        engine.dispose()
    finally:
        _restore_env(previous_url, previous_env)


def test_0032_recovers_stale_alembic_batch_table_with_foreign_keys_and_dependent_rows(tmp_path) -> None:
    db_path = tmp_path / "partial-0032-batch.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url, previous_env = _set_env(database_url)
    try:
        command.upgrade(_config(), "0031_meal_completion_finalization")
        engine = _engine(database_url)
        _seed_dependent_inventory(engine)
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE meal_completions ADD COLUMN actual_servings_produced NUMERIC(10, 3)"))
            connection.execute(text("ALTER TABLE meal_completions ADD COLUMN actual_servings_eaten NUMERIC(10, 3)"))
            connection.execute(text("ALTER TABLE meal_completions ADD COLUMN production_committed_at DATETIME"))
            connection.execute(text("ALTER TABLE inventory_lots ADD COLUMN source_type VARCHAR(30)"))
            connection.execute(text("ALTER TABLE inventory_lots ADD COLUMN source_id INTEGER"))
            connection.execute(text("ALTER TABLE inventory_lots ADD COLUMN source_name VARCHAR(160)"))
            connection.execute(text("UPDATE inventory_lots SET source_type='INGREDIENT' WHERE source_type IS NULL"))
            connection.execute(text("CREATE TABLE _alembic_tmp_inventory_lots AS SELECT * FROM inventory_lots WHERE 0"))
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0031_meal_completion_finalization"
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        command.upgrade(_config(), "head")
        _assert_recovered(engine)
        engine.dispose()
    finally:
        _restore_env(previous_url, previous_env)


def test_0033_recovers_after_partial_additive_sqlite_ddl(tmp_path) -> None:
    db_path = tmp_path / "partial-0033.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url, previous_env = _set_env(database_url)
    try:
        command.upgrade(_config(), "0032_completion_leftovers_outputs")
        engine = _engine(database_url)
        _seed_dependent_inventory(engine)
        with engine.begin() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0032_completion_leftovers_outputs"
            connection.execute(text("ALTER TABLE planned_meals ADD COLUMN source_type VARCHAR(30) DEFAULT 'SAVED_MEAL' NOT NULL"))
            connection.execute(text("ALTER TABLE planned_meals ADD COLUMN source_origin_planned_meal_id INTEGER"))
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        command.upgrade(_config(), "head")
        _assert_recovered(engine)
        engine.dispose()
    finally:
        _restore_env(previous_url, previous_env)


def test_0034_recovers_after_partial_additive_sqlite_ddl_with_foreign_keys_on(tmp_path) -> None:
    db_path = tmp_path / "partial-0034.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url, previous_env = _set_env(database_url)
    try:
        command.upgrade(_config(), "0033_leftover_coverage")
        engine = _engine(database_url)
        _seed_dependent_inventory(engine)
        with engine.begin() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0033_leftover_coverage"
            connection.execute(text("ALTER TABLE meal_cycles ADD COLUMN lifecycle_status VARCHAR(20) DEFAULT 'DRAFT' NOT NULL"))
            connection.execute(text("ALTER TABLE meal_cycles ADD COLUMN activated_at DATETIME"))
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        command.upgrade(_config(), "head")
        _assert_recovered(engine)
        engine.dispose()
    finally:
        _restore_env(previous_url, previous_env)


def test_0035_recovers_partial_columns_and_stale_batch_with_populated_dependents(tmp_path) -> None:
    db_path = tmp_path / "partial-0035.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url, previous_env = _set_env(database_url)
    try:
        command.upgrade(_config(), "0034_cycle_lifecycle")
        engine = _engine(database_url)
        _seed_dependent_inventory(engine)
        _seed_dependent_planning(engine)
        with engine.begin() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0034_cycle_lifecycle"
            connection.execute(text("ALTER TABLE planned_meals ADD COLUMN source_recipe_id INTEGER"))
            connection.execute(text("CREATE TABLE _alembic_tmp_planned_meals AS SELECT * FROM planned_meals WHERE 0"))
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        command.upgrade(_config(), "head")
        _assert_recovered(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT snapshot_name FROM planned_meals WHERE id=9902")).scalar_one() == "Migration Meal"
            assert connection.execute(text("SELECT planned_meal_id FROM meal_completions WHERE id=9902")).scalar_one() == 9902
            leftover = connection.execute(text("SELECT planned_meal_id, source_meal_id, source_recipe_id FROM leftovers WHERE id=9902")).one()
            assert leftover.planned_meal_id == 9902 and leftover.source_meal_id == 9902 and leftover.source_recipe_id is None
        engine.dispose()
    finally:
        _restore_env(previous_url, previous_env)
