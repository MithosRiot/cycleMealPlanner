"""add direct Recipe occurrence storage

Revision ID: 0035_direct_recipe_occurrences
Revises: 0034_cycle_lifecycle
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0035_direct_recipe_occurrences"
down_revision: Union[str, None] = "0034_cycle_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_map(bind, table_name: str) -> dict[str, dict]:
    return {row["name"]: row for row in sa.inspect(bind).get_columns(table_name)}


def _recover_stale_batch_table(bind, table_name: str) -> None:
    temp_name = f"_alembic_tmp_{table_name}"
    tables = set(sa.inspect(bind).get_table_names())
    if temp_name not in tables:
        return
    if table_name in tables:
        bind.execute(sa.text(f'DROP TABLE "{temp_name}"'))
    else:
        bind.execute(sa.text(f'ALTER TABLE "{temp_name}" RENAME TO "{table_name}"'))


def _sqlite_foreign_keys_enabled(bind) -> bool:
    return bind.dialect.name == "sqlite" and bool(bind.exec_driver_sql("PRAGMA foreign_keys").scalar())


def _set_sqlite_foreign_keys(bind, enabled: bool) -> None:
    if bind.dialect.name != "sqlite":
        return
    value = "ON" if enabled else "OFF"
    with op.get_context().autocommit_block():
        bind.exec_driver_sql(f"PRAGMA foreign_keys={value}")
    if bool(bind.exec_driver_sql("PRAGMA foreign_keys").scalar()) != enabled:
        raise RuntimeError(f"Could not set SQLite foreign_keys={value} for migration 0035")


def _assert_sqlite_foreign_keys_valid(bind) -> None:
    if bind.dialect.name != "sqlite":
        return
    violations = bind.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"SQLite foreign key violations after migration 0035: {violations}")


def upgrade() -> None:
    bind = op.get_bind()
    _recover_stale_batch_table(bind, "planned_meals")
    _recover_stale_batch_table(bind, "leftovers")

    planned_columns = _column_map(bind, "planned_meals")
    if "source_recipe_id" not in planned_columns:
        # Provenance is validated at the application layer. Keep this additive
        # column free of a SQLite ALTER-time FK, matching other additive source
        # provenance columns in the planner.
        op.add_column("planned_meals", sa.Column("source_recipe_id", sa.Integer(), nullable=True))

    leftover_columns = _column_map(bind, "leftovers")
    if "source_recipe_id" not in leftover_columns:
        op.add_column("leftovers", sa.Column("source_recipe_id", sa.Integer(), nullable=True))

    planned_columns = _column_map(bind, "planned_meals")
    leftover_columns = _column_map(bind, "leftovers")
    planned_meal_needs_nullable = not bool(planned_columns["meal_id"].get("nullable"))
    leftover_meal_needs_nullable = not bool(leftover_columns["source_meal_id"].get("nullable"))

    foreign_keys_were_enabled = _sqlite_foreign_keys_enabled(bind)
    if foreign_keys_were_enabled and (planned_meal_needs_nullable or leftover_meal_needs_nullable):
        _set_sqlite_foreign_keys(bind, False)

    try:
        if planned_meal_needs_nullable:
            _recover_stale_batch_table(bind, "planned_meals")
            with op.batch_alter_table("planned_meals") as batch:
                batch.alter_column("meal_id", existing_type=sa.Integer(), nullable=True)

        if leftover_meal_needs_nullable:
            _recover_stale_batch_table(bind, "leftovers")
            with op.batch_alter_table("leftovers") as batch:
                batch.alter_column("source_meal_id", existing_type=sa.Integer(), nullable=True)

        _assert_sqlite_foreign_keys_valid(bind)
    finally:
        if foreign_keys_were_enabled and (planned_meal_needs_nullable or leftover_meal_needs_nullable):
            _set_sqlite_foreign_keys(bind, True)

    _assert_sqlite_foreign_keys_valid(bind)


def downgrade() -> None:
    bind = op.get_bind()
    direct_planned_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM planned_meals WHERE meal_id IS NULL OR source_recipe_id IS NOT NULL"
    )).scalar()
    direct_leftover_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM leftovers WHERE source_meal_id IS NULL OR source_recipe_id IS NOT NULL"
    )).scalar()
    if direct_planned_count or direct_leftover_count:
        raise RuntimeError("Cannot downgrade 0035 while direct Recipe occurrence data exists")

    foreign_keys_were_enabled = _sqlite_foreign_keys_enabled(bind)
    if foreign_keys_were_enabled:
        _set_sqlite_foreign_keys(bind, False)
    try:
        with op.batch_alter_table("leftovers") as batch:
            batch.alter_column("source_meal_id", existing_type=sa.Integer(), nullable=False)
            batch.drop_column("source_recipe_id")
        with op.batch_alter_table("planned_meals") as batch:
            batch.alter_column("meal_id", existing_type=sa.Integer(), nullable=False)
            batch.drop_column("source_recipe_id")
    finally:
        if foreign_keys_were_enabled:
            _set_sqlite_foreign_keys(bind, True)
    _assert_sqlite_foreign_keys_valid(bind)
