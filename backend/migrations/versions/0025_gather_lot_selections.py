"""exact lot gather selections

Revision ID: 0025_gather_lot_selections
Revises: 0024_prep_reminders
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0025_gather_lot_selections"
down_revision: Union[str, None] = "0024_prep_reminders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gather_lot_selections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("planned_meal_id", sa.Integer(), sa.ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meal_recipe_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipe_ingredient_id", sa.Integer(), sa.ForeignKey("recipe_ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_gather_selection_quantity_positive"),
        sa.UniqueConstraint(
            "planned_meal_id", "meal_recipe_id", "recipe_ingredient_id", "lot_id",
            name="uq_gather_selection_requirement_lot",
        ),
    )
    op.create_index("ix_gather_selection_lot", "gather_lot_selections", ["lot_id"])
    op.create_index("ix_gather_selection_planned_meal", "gather_lot_selections", ["planned_meal_id"])


def downgrade() -> None:
    op.drop_index("ix_gather_selection_planned_meal", table_name="gather_lot_selections")
    op.drop_index("ix_gather_selection_lot", table_name="gather_lot_selections")
    op.drop_table("gather_lot_selections")
