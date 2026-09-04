"""add completion leftovers and produced outputs

Revision ID: 0032_completion_leftovers_outputs
Revises: 0031_meal_completion_finalization
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032_completion_leftovers_outputs"
down_revision: Union[str, None] = "0031_meal_completion_finalization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_map(bind, table_name: str) -> dict[str, dict]:
    return {row["name"]: row for row in sa.inspect(bind).get_columns(table_name)}


def _check_map(bind, table_name: str) -> dict[str, dict]:
    return {
        row["name"]: row
        for row in sa.inspect(bind).get_check_constraints(table_name)
        if row.get("name")
    }


def _recover_stale_batch_table(bind, table_name: str) -> None:
    """Recover an Alembic SQLite batch table left by interrupted DDL.

    Alembic batch mode creates ``_alembic_tmp_<table>`` before copying and
    replacing the original table. SQLite DDL is non-transactional, so an
    interrupted migration can leave that temporary table behind. If the real
    table still exists, the temporary table is incomplete/redundant and is
    safe to drop. If only the temporary table exists, restore it as the real
    table so the migration can continue without discarding copied data.
    """
    temp_name = f"_alembic_tmp_{table_name}"
    tables = set(sa.inspect(bind).get_table_names())
    if temp_name not in tables:
        return
    if table_name in tables:
        bind.execute(sa.text(f'DROP TABLE "{temp_name}"'))
    else:
        bind.execute(sa.text(f'ALTER TABLE "{temp_name}" RENAME TO "{table_name}"'))


def upgrade() -> None:
    """Apply 0032 safely even after an interrupted SQLite DDL migration.

    SQLite DDL is non-transactional in this app. If a prior 0032 attempt stops
    after one or more ALTER/CREATE statements, Alembic can still report 0031
    while part of the 0032 schema already exists. Every step below therefore
    inspects the live schema/data before applying the corresponding change.
    """
    bind = op.get_bind()

    # Clean up/restore known Alembic batch artifacts before inspecting schema.
    # These are the two tables altered with batch mode by this migration.
    _recover_stale_batch_table(bind, "inventory_lots")
    _recover_stale_batch_table(bind, "inventory_transactions")

    completion_columns = _column_map(bind, "meal_completions")
    if "actual_servings_produced" not in completion_columns:
        op.add_column("meal_completions", sa.Column("actual_servings_produced", sa.Numeric(10, 3), nullable=True))
    if "actual_servings_eaten" not in completion_columns:
        op.add_column("meal_completions", sa.Column("actual_servings_eaten", sa.Numeric(10, 3), nullable=True))
    if "production_committed_at" not in completion_columns:
        op.add_column("meal_completions", sa.Column("production_committed_at", sa.DateTime(), nullable=True))

    lot_columns = _column_map(bind, "inventory_lots")
    if "source_type" not in lot_columns:
        op.add_column("inventory_lots", sa.Column("source_type", sa.String(length=30), nullable=True))
    if "source_id" not in lot_columns:
        op.add_column("inventory_lots", sa.Column("source_id", sa.Integer(), nullable=True))
    if "source_name" not in lot_columns:
        op.add_column("inventory_lots", sa.Column("source_name", sa.String(length=160), nullable=True))

    op.execute("UPDATE inventory_lots SET source_type='INGREDIENT' WHERE source_type IS NULL")

    lot_columns = _column_map(bind, "inventory_lots")
    lot_checks = _check_map(bind, "inventory_lots")
    ingredient_needs_nullable = not bool(lot_columns["ingredient_id"].get("nullable"))
    source_needs_required = bool(lot_columns["source_type"].get("nullable"))
    source_default = lot_columns["source_type"].get("default")
    source_needs_default = source_default is None or "INGREDIENT" not in str(source_default)
    needs_source_type_check = "ck_inventory_lots_source_type" not in lot_checks
    needs_source_identity_check = "ck_inventory_lots_source_identity" not in lot_checks

    if any((ingredient_needs_nullable, source_needs_required, source_needs_default, needs_source_type_check, needs_source_identity_check)):
        _recover_stale_batch_table(bind, "inventory_lots")
        with op.batch_alter_table("inventory_lots") as batch:
            if ingredient_needs_nullable:
                batch.alter_column("ingredient_id", existing_type=sa.Integer(), nullable=True)
            if source_needs_required or source_needs_default:
                batch.alter_column(
                    "source_type",
                    existing_type=sa.String(length=30),
                    nullable=False,
                    server_default="INGREDIENT",
                )
            if needs_source_type_check:
                batch.create_check_constraint(
                    "ck_inventory_lots_source_type",
                    "source_type IN ('INGREDIENT','LEFTOVER','RECIPE_OUTPUT')",
                )
            if needs_source_identity_check:
                batch.create_check_constraint(
                    "ck_inventory_lots_source_identity",
                    "(source_type='INGREDIENT' AND ingredient_id IS NOT NULL) OR (source_type!='INGREDIENT' AND source_id IS NOT NULL)",
                )

    transaction_checks = _check_map(bind, "inventory_transactions")
    transaction_type_check = transaction_checks.get("ck_inventory_transactions_type")
    transaction_sql = str(transaction_type_check.get("sqltext", "")) if transaction_type_check else ""
    if "PRODUCTION" not in transaction_sql:
        _recover_stale_batch_table(bind, "inventory_transactions")
        with op.batch_alter_table("inventory_transactions") as batch:
            if transaction_type_check is not None:
                batch.drop_constraint("ck_inventory_transactions_type", type_="check")
            batch.create_check_constraint(
                "ck_inventory_transactions_type",
                "transaction_type IN ('PURCHASE','CONSUME','TRANSFER','MANUAL_ADD','MANUAL_REMOVE','CORRECTION','PRODUCTION')",
            )

    serving_unit_id = bind.execute(sa.text("SELECT id FROM measurement_units WHERE code='serving' LIMIT 1")).scalar()
    if serving_unit_id is None:
        id_16_in_use = bind.execute(sa.text("SELECT id FROM measurement_units WHERE id=16 LIMIT 1")).scalar()
        if id_16_in_use is None:
            bind.execute(sa.text(
                "INSERT INTO measurement_units (id, code, name, unit_family, base_multiplier, allows_fraction) "
                "VALUES (16, 'serving', 'serving', 'SERVING', 1, 1)"
            ))
        else:
            bind.execute(sa.text(
                "INSERT INTO measurement_units (code, name, unit_family, base_multiplier, allows_fraction) "
                "VALUES ('serving', 'serving', 'SERVING', 1, 1)"
            ))

    tables = set(sa.inspect(bind).get_table_names())
    if "leftovers" not in tables:
        op.create_table(
            "leftovers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("completion_id", sa.Integer(), sa.ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("planned_meal_id", sa.Integer(), sa.ForeignKey("planned_meals.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("source_meal_id", sa.Integer(), sa.ForeignKey("meals.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("source_meal_name", sa.String(length=160), nullable=False),
            sa.Column("source_components", sa.Text(), nullable=False),
            sa.Column("actual_servings_produced", sa.Numeric(10, 3), nullable=False),
            sa.Column("actual_servings_eaten", sa.Numeric(10, 3), nullable=False),
            sa.Column("leftover_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("serving_unit", sa.String(length=40), nullable=False, server_default="serving"),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("expiration_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="AVAILABLE"),
            sa.Column("inventory_lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=True, unique=True),
            sa.Column("inventory_transaction_id", sa.Integer(), sa.ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("actual_servings_produced >= 0", name="ck_leftovers_produced_nonnegative"),
            sa.CheckConstraint("actual_servings_eaten >= 0", name="ck_leftovers_eaten_nonnegative"),
            sa.CheckConstraint("actual_servings_eaten <= actual_servings_produced", name="ck_leftovers_eaten_not_over_produced"),
            sa.CheckConstraint("leftover_servings >= 0", name="ck_leftovers_quantity_nonnegative"),
            sa.CheckConstraint("status IN ('NONE','AVAILABLE')", name="ck_leftovers_status"),
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "meal_completion_outputs" not in tables:
        op.create_table(
            "meal_completion_outputs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("completion_id", sa.Integer(), sa.ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("component_key", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("recipe_name", sa.String(length=160), nullable=False),
            sa.Column("recipe_output_id", sa.Integer(), sa.ForeignKey("recipe_outputs.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("output_name", sa.String(length=160), nullable=False),
            sa.Column("recipe_base_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("planned_component_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("base_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("calculated_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("actual_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("quantity_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("unit_code", sa.String(length=30), nullable=False),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("expiration_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("inventory_lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=True, unique=True),
            sa.Column("inventory_transaction_id", sa.Integer(), sa.ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("completion_id", "component_key", "recipe_output_id", name="uq_meal_completion_outputs_source"),
            sa.CheckConstraint("recipe_base_servings > 0", name="ck_meal_completion_outputs_base_servings_positive"),
            sa.CheckConstraint("planned_component_servings >= 0", name="ck_meal_completion_outputs_component_servings_nonnegative"),
            sa.CheckConstraint("base_quantity >= 0", name="ck_meal_completion_outputs_base_quantity_nonnegative"),
            sa.CheckConstraint("calculated_quantity >= 0", name="ck_meal_completion_outputs_calculated_nonnegative"),
            sa.CheckConstraint("actual_quantity >= 0", name="ck_meal_completion_outputs_actual_nonnegative"),
        )


def downgrade() -> None:
    op.drop_table("meal_completion_outputs")
    op.drop_table("leftovers")
    op.execute("DELETE FROM measurement_units WHERE code='serving'")
    with op.batch_alter_table("inventory_transactions") as batch:
        batch.drop_constraint("ck_inventory_transactions_type", type_="check")
        batch.create_check_constraint(
            "ck_inventory_transactions_type",
            "transaction_type IN ('PURCHASE','CONSUME','TRANSFER','MANUAL_ADD','MANUAL_REMOVE','CORRECTION')",
        )
    with op.batch_alter_table("inventory_lots") as batch:
        batch.drop_constraint("ck_inventory_lots_source_identity", type_="check")
        batch.drop_constraint("ck_inventory_lots_source_type", type_="check")
        batch.drop_column("source_name")
        batch.drop_column("source_id")
        batch.drop_column("source_type")
        batch.alter_column("ingredient_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("meal_completions", "production_committed_at")
    op.drop_column("meal_completions", "actual_servings_eaten")
    op.drop_column("meal_completions", "actual_servings_produced")
