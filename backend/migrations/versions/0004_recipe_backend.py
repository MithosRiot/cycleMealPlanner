"""recipe backend

Revision ID: 0004_recipe_backend
Revises: 0003_ingredients_and_tags
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_recipe_backend"
down_revision: str | None = "0003_ingredients_and_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_servings", sa.Numeric(10, 3), nullable=False),
        sa.Column("serving_unit", sa.String(length=40), nullable=False, server_default="servings"),
        sa.Column("yield_quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("yield_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prep_time_minutes", sa.Integer(), nullable=True),
        sa.Column("cook_time_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_recipes_household_normalized_name"),
        sa.CheckConstraint("base_servings > 0", name="ck_recipes_base_servings_positive"),
        sa.CheckConstraint("yield_quantity IS NULL OR yield_quantity > 0", name="ck_recipes_yield_quantity_positive"),
        sa.CheckConstraint("prep_time_minutes IS NULL OR prep_time_minutes >= 0", name="ck_recipes_prep_time_nonnegative"),
        sa.CheckConstraint("cook_time_minutes IS NULL OR cook_time_minutes >= 0", name="ck_recipes_cook_time_nonnegative"),
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("display_text", sa.String(length=160), nullable=True),
        sa.Column("preparation", sa.String(length=160), nullable=True),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("scaling_mode", sa.String(length=20), nullable=False, server_default="LINEAR"),
        sa.Column("required_state", sa.String(length=30), nullable=False, server_default="ANY"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("quantity >= 0", name="ck_recipe_ingredients_quantity_nonnegative"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_ingredients_sort_order_nonnegative"),
        sa.CheckConstraint("scaling_mode IN ('LINEAR','FIXED','ROUND_UP','MANUAL')", name="ck_recipe_ingredients_scaling_mode"),
    )

    op.create_table(
        "recipe_meal_types",
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("meal_type", sa.String(length=30), primary_key=True),
    )

    op.create_table(
        "recipe_tags",
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("recipe_tags")
    op.drop_table("recipe_meal_types")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
