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


def upgrade() -> None:
    op.add_column("meal_completions", sa.Column("actual_servings_produced", sa.Numeric(10, 3), nullable=True))
    op.add_column("meal_completions", sa.Column("actual_servings_eaten", sa.Numeric(10, 3), nullable=True))
    op.add_column("meal_completions", sa.Column("production_committed_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("inventory_lots") as batch:
        batch.add_column(sa.Column("source_type", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("source_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source_name", sa.String(length=160), nullable=True))
        batch.alter_column("ingredient_id", existing_type=sa.Integer(), nullable=True)
    op.execute("UPDATE inventory_lots SET source_type='INGREDIENT' WHERE source_type IS NULL")
    with op.batch_alter_table("inventory_lots") as batch:
        batch.alter_column("source_type", existing_type=sa.String(length=30), nullable=False, server_default="INGREDIENT")
        batch.create_check_constraint("ck_inventory_lots_source_type", "source_type IN ('INGREDIENT','LEFTOVER','RECIPE_OUTPUT')")
        batch.create_check_constraint(
            "ck_inventory_lots_source_identity",
            "(source_type='INGREDIENT' AND ingredient_id IS NOT NULL) OR (source_type!='INGREDIENT' AND source_id IS NOT NULL)",
        )

    with op.batch_alter_table("inventory_transactions") as batch:
        batch.drop_constraint("ck_inventory_transactions_type", type_="check")
        batch.create_check_constraint(
            "ck_inventory_transactions_type",
            "transaction_type IN ('PURCHASE','CONSUME','TRANSFER','MANUAL_ADD','MANUAL_REMOVE','CORRECTION','PRODUCTION')",
        )

    units = sa.table(
        "measurement_units",
        sa.column("id", sa.Integer), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("unit_family", sa.String), sa.column("base_multiplier", sa.Numeric), sa.column("allows_fraction", sa.Boolean),
    )
    op.bulk_insert(units, [{
        "id": 16, "code": "serving", "name": "serving", "unit_family": "SERVING",
        "base_multiplier": 1, "allows_fraction": True,
    }])

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
    op.execute("DELETE FROM measurement_units WHERE id=16 AND code='serving'")
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
