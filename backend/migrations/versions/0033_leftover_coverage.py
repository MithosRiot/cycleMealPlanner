"""add produced-source planning and coverage reservations

Revision ID: 0033_leftover_coverage
Revises: 0032_completion_leftovers_outputs
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0033_leftover_coverage"
down_revision: Union[str, None] = "0032_completion_leftovers_outputs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "planned_meals")
    if "source_type" not in columns:
        op.add_column("planned_meals", sa.Column("source_type", sa.String(length=30), nullable=False, server_default="SAVED_MEAL"))
    if "source_origin_planned_meal_id" not in columns:
        op.add_column("planned_meals", sa.Column("source_origin_planned_meal_id", sa.Integer(), nullable=True))
    if "source_recipe_output_id" not in columns:
        op.add_column("planned_meals", sa.Column("source_recipe_output_id", sa.Integer(), nullable=True))
    if "source_quantity" not in columns:
        op.add_column("planned_meals", sa.Column("source_quantity", sa.Numeric(14, 6), nullable=True))
    if "source_unit_id" not in columns:
        op.add_column("planned_meals", sa.Column("source_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=True))

    tables = set(sa.inspect(bind).get_table_names())
    if "production_coverage_reservations" not in tables:
        op.create_table(
            "production_coverage_reservations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("planned_meal_id", sa.Integer(), nullable=False),
            sa.Column("cycle_slot_id", sa.Integer(), nullable=False),
            sa.Column("source_origin_planned_meal_id", sa.Integer(), nullable=False),
            sa.Column("source_type", sa.String(length=30), nullable=False),
            sa.Column("source_record_id", sa.Integer(), nullable=True),
            sa.Column("source_recipe_output_id", sa.Integer(), nullable=True),
            sa.Column("lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("requested_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("reserved_quantity", sa.Numeric(14, 6), nullable=False, server_default="0"),
            sa.Column("shortage_quantity", sa.Numeric(14, 6), nullable=False, server_default="0"),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.Column("release_reason", sa.String(length=40), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("released_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("source_type IN ('LEFTOVER','RECIPE_OUTPUT')", name="ck_production_coverage_source_type"),
            sa.CheckConstraint("requested_quantity > 0", name="ck_production_coverage_requested_positive"),
            sa.CheckConstraint("reserved_quantity >= 0", name="ck_production_coverage_reserved_nonnegative"),
            sa.CheckConstraint("shortage_quantity >= 0", name="ck_production_coverage_shortage_nonnegative"),
            sa.CheckConstraint("status IN ('ACTIVE','RELEASED')", name="ck_production_coverage_status"),
        )
        op.create_index("ix_production_coverage_planned_meal", "production_coverage_reservations", ["planned_meal_id", "status"])
        op.create_index("ix_production_coverage_origin", "production_coverage_reservations", ["source_origin_planned_meal_id", "status"])
        op.create_index("ix_production_coverage_lot", "production_coverage_reservations", ["lot_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_production_coverage_lot", table_name="production_coverage_reservations")
    op.drop_index("ix_production_coverage_origin", table_name="production_coverage_reservations")
    op.drop_index("ix_production_coverage_planned_meal", table_name="production_coverage_reservations")
    op.drop_table("production_coverage_reservations")
    op.drop_column("planned_meals", "source_unit_id")
    op.drop_column("planned_meals", "source_quantity")
    op.drop_column("planned_meals", "source_recipe_output_id")
    op.drop_column("planned_meals", "source_origin_planned_meal_id")
    op.drop_column("planned_meals", "source_type")
