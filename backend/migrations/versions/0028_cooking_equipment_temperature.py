"""add cooking equipment and temperature context

Revision ID: 0028_cooking_equipment_temperature
Revises: 0027_cooking_timers
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0028_cooking_equipment_temperature"
down_revision: Union[str, None] = "0027_cooking_timers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "recipe_cooking_step_equipment" not in tables:
        op.create_table(
            "recipe_cooking_step_equipment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cooking_step_id", sa.Integer(), sa.ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recipe_equipment_id", sa.Integer(), sa.ForeignKey("recipe_equipment.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("cooking_step_id", "recipe_equipment_id", name="uq_recipe_cooking_step_equipment"),
            sa.CheckConstraint("sort_order >= 0", name="ck_recipe_cooking_step_equipment_sort_order_nonnegative"),
        )
    if "recipe_cooking_temperatures" not in tables:
        op.create_table(
            "recipe_cooking_temperatures",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cooking_step_id", sa.Integer(), sa.ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(length=80), nullable=False, server_default="temperature"),
            sa.Column("value", sa.Numeric(8, 2), nullable=False),
            sa.Column("unit", sa.String(length=1), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.CheckConstraint("unit IN ('F','C')", name="ck_recipe_cooking_temperatures_unit"),
            sa.CheckConstraint("sort_order >= 0", name="ck_recipe_cooking_temperatures_sort_order_nonnegative"),
        )


def downgrade() -> None:
    op.drop_table("recipe_cooking_temperatures")
    op.drop_table("recipe_cooking_step_equipment")
