"""add Meal Cycle lifecycle state

Revision ID: 0034_cycle_lifecycle
Revises: 0033_leftover_coverage
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034_cycle_lifecycle"
down_revision: Union[str, None] = "0033_leftover_coverage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "meal_cycles")
    # Keep the original `status` column in place for SQLite upgrade safety. It
    # has an old DRAFT-only CHECK constraint that would require rebuilding the
    # parent table while many populated child tables reference it. The new
    # additive lifecycle_status column is authoritative from v1.0 onward.
    if "lifecycle_status" not in columns:
        op.add_column(
            "meal_cycles",
            sa.Column("lifecycle_status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        )
    if "activated_at" not in columns:
        op.add_column("meal_cycles", sa.Column("activated_at", sa.DateTime(), nullable=True))
    if "completed_at" not in columns:
        op.add_column("meal_cycles", sa.Column("completed_at", sa.DateTime(), nullable=True))
    if "cancelled_at" not in columns:
        op.add_column("meal_cycles", sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("meal_cycles", "cancelled_at")
    op.drop_column("meal_cycles", "completed_at")
    op.drop_column("meal_cycles", "activated_at")
    op.drop_column("meal_cycles", "lifecycle_status")
