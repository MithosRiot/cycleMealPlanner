"""shopping lists

Revision ID: 0010_shopping_lists
Revises: 0009_planned_servings_leftovers
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_shopping_lists"
down_revision = "0009_planned_servings_leftovers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meal_cycle_id", sa.Integer(), sa.ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "shopping_list_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shopping_list_id", sa.Integer(), sa.ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("shopping_category_id", sa.Integer(), sa.ForeignKey("shopping_categories.id", ondelete="SET NULL")),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("unit_family", sa.String(length=20), nullable=False),
        sa.Column("required_quantity", sa.Numeric(16, 6), nullable=False),
        sa.Column("inventory_quantity", sa.Numeric(16, 6), nullable=False),
        sa.Column("generated_quantity", sa.Numeric(16, 6), nullable=False),
        sa.Column("adjustment_quantity", sa.Numeric(16, 6), nullable=False, server_default="0"),
        sa.Column("source_trace", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("warning", sa.Text()),
        sa.UniqueConstraint("shopping_list_id", "ingredient_id", "unit_family", name="uq_shopping_item_ingredient_family"),
    )


def downgrade() -> None:
    op.drop_table("shopping_list_items")
    op.drop_table("shopping_lists")
