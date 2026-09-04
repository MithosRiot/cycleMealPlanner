"""add meal completion finalization persistence

Revision ID: 0031_meal_completion_finalization
Revises: 0030_meal_completion_drafts
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0031_meal_completion_finalization"
down_revision: Union[str, None] = "0030_meal_completion_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    completion_columns = {row["name"] for row in inspector.get_columns("meal_completions")}
    if "finalized_at" not in completion_columns:
        op.add_column("meal_completions", sa.Column("finalized_at", sa.DateTime(), nullable=True))

    tables = set(inspector.get_table_names())
    if "meal_completion_allocations" not in tables:
        op.create_table(
            "meal_completion_allocations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("completion_id", sa.Integer(), sa.ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("usage_id", sa.Integer(), sa.ForeignKey("meal_completion_usage.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("inventory_transaction_id", sa.Integer(), sa.ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
            sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("unit_code", sa.String(length=30), nullable=False),
            sa.Column("source_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("source_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("source_unit_code", sa.String(length=30), nullable=False),
            sa.CheckConstraint("quantity > 0", name="ck_meal_completion_allocations_quantity_positive"),
            sa.CheckConstraint("source_quantity > 0", name="ck_meal_completion_allocations_source_quantity_positive"),
        )


def downgrade() -> None:
    op.drop_table("meal_completion_allocations")
    op.drop_column("meal_completions", "finalized_at")
