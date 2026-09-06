from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini")); config.set_main_option("script_location", str(BACKEND_DIR / "migrations")); config.set_main_option("sqlalchemy.url", url); return config


def test_0037_recovers_partial_additive_ddl_with_populated_foreign_keys(tmp_path, monkeypatch) -> None:
    path = tmp_path / "shopping-partial-recovery.db"; url = f"sqlite:///{path.as_posix()}"; monkeypatch.setenv("CYCLE_MEAL_PLANNER_DATABASE_URL", url); monkeypatch.setenv("CYCLE_MEAL_PLANNER_ENV", "migration-recovery-test"); config = _config(url); command.upgrade(config, "0036_active_cycle_shopping_deltas"); engine = create_engine(url)
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor(); cursor.execute("PRAGMA foreign_keys=ON"); cursor.close()
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE shopping_item_purchases ADD COLUMN purchased_ingredient_id INTEGER"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(); columns = {row[1] for row in connection.execute(text("PRAGMA table_info(shopping_item_purchases)"))}; violations = connection.execute(text("PRAGMA foreign_key_check")).all()
    assert version == "0037_shopping_partial_substitutions"; assert {"purchased_ingredient_id", "satisfied_quantity", "satisfied_unit_id", "purchase_kind", "idempotency_key"}.issubset(columns); assert violations == []
