"""add cooking timers

Revision ID: 0027_cooking_timers
Revises: 0026_recipe_cooking_steps
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0027_cooking_timers"
down_revision: Union[str, None] = "0026_recipe_cooking_steps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "recipe_cooking_timers" not in tables:
        op.create_table(
            "recipe_cooking_timers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cooking_step_id", sa.Integer(), sa.ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(length=160), nullable=False),
            sa.Column("duration_seconds", sa.Integer(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.CheckConstraint("duration_seconds > 0", name="ck_recipe_cooking_timers_duration_positive"),
            sa.CheckConstraint("sort_order >= 0", name="ck_recipe_cooking_timers_sort_order_nonnegative"),
        )
    if "planned_cooking_timers" not in tables:
        op.create_table(
            "planned_cooking_timers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("planned_meal_id", sa.Integer(), sa.ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cooking_timer_id", sa.Integer(), sa.ForeignKey("recipe_cooking_timers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="READY"),
            sa.Column("remaining_seconds", sa.Integer(), nullable=False),
            sa.Column("ends_at_epoch", sa.Integer(), nullable=True),
            sa.UniqueConstraint("planned_meal_id", "cooking_timer_id", name="uq_planned_cooking_timers_meal_timer"),
            sa.CheckConstraint("status IN ('READY','RUNNING','PAUSED','COMPLETED','DISMISSED')", name="ck_planned_cooking_timers_status"),
            sa.CheckConstraint("remaining_seconds >= 0", name="ck_planned_cooking_timers_remaining_nonnegative"),
        )


def downgrade() -> None:
    op.drop_table("planned_cooking_timers")
    op.drop_table("recipe_cooking_timers")
