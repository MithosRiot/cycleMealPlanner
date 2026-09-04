"""add meal completion drafts

Revision ID: 0030_meal_completion_drafts
Revises: 0029_cooking_coordination
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0030_meal_completion_drafts"
down_revision: Union[str, None] = "0029_cooking_coordination"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "meal_completions" not in tables:
        op.create_table(
            "meal_completions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("planned_meal_id", sa.Integer(), sa.ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
            sa.Column("plan_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("snapshot_name", sa.String(length=160), nullable=False),
            sa.Column("snapshot_planned_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("snapshot_planned_leftover_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("snapshot_scaled_components", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("status IN ('DRAFT','FINALIZED')", name="ck_meal_completions_status"),
        )
    if "meal_completion_usage" not in tables:
        op.create_table(
            "meal_completion_usage",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("completion_id", sa.Integer(), sa.ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("component_key", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("recipe_name", sa.String(length=160), nullable=False),
            sa.Column("recipe_ingredient_id", sa.Integer(), nullable=False),
            sa.Column("planned_ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("planned_ingredient_name", sa.String(length=120), nullable=False),
            sa.Column("planned_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("planned_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("planned_unit_code", sa.String(length=30), nullable=False),
            sa.Column("actual_ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("actual_ingredient_name", sa.String(length=120), nullable=False),
            sa.Column("actual_quantity", sa.Numeric(14, 6), nullable=False),
            sa.Column("actual_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("actual_unit_code", sa.String(length=30), nullable=False),
            sa.Column("preparation", sa.String(length=160), nullable=True),
            sa.Column("prep_method", sa.String(length=80), nullable=True),
            sa.Column("prep_size", sa.String(length=80), nullable=True),
            sa.Column("prep_state", sa.String(length=80), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.UniqueConstraint("completion_id", "component_key", "recipe_ingredient_id", name="uq_meal_completion_usage_source"),
            sa.CheckConstraint("planned_quantity >= 0", name="ck_meal_completion_usage_planned_nonnegative"),
            sa.CheckConstraint("actual_quantity >= 0", name="ck_meal_completion_usage_actual_nonnegative"),
        )


def downgrade() -> None:
    op.drop_table("meal_completion_usage")
    op.drop_table("meal_completions")
