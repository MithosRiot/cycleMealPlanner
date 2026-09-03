"""add recipe cooking steps

Revision ID: 0026_recipe_cooking_steps
Revises: 0025_gather_lot_selections
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0026_recipe_cooking_steps"
down_revision: Union[str, None] = "0025_gather_lot_selections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "recipe_cooking_steps" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "recipe_cooking_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prep_group_id", sa.Integer(), sa.ForeignKey("recipe_prep_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_cooking_steps_sort_order_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("recipe_cooking_steps")
