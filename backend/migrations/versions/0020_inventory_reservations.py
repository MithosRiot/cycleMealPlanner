"""inventory reservations

Revision ID: 0020_inventory_reservations
Revises: 0019_recipe_outputs_dependencies
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020_inventory_reservations"
down_revision: Union[str, None] = "0019_recipe_outputs_dependencies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planned_meal_id", sa.Integer(), sa.ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meal_recipe_id", sa.Integer(), nullable=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipe_ingredient_id", sa.Integer(), nullable=True),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_reservations_quantity_nonnegative"),
        sa.CheckConstraint("status IN ('ACTIVE','RELEASED')", name="ck_inventory_reservations_status"),
        sa.UniqueConstraint("planned_meal_id", "meal_recipe_id", "recipe_ingredient_id", name="uq_inventory_reservations_source"),
    )
    op.create_index("ix_inventory_reservations_cycle_status", "inventory_reservations", ["cycle_id", "status"])
    op.create_index("ix_inventory_reservations_ingredient_status", "inventory_reservations", ["ingredient_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_inventory_reservations_ingredient_status", table_name="inventory_reservations")
    op.drop_index("ix_inventory_reservations_cycle_status", table_name="inventory_reservations")
    op.drop_table("inventory_reservations")
