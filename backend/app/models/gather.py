from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GatherLotSelection(Base):
    __tablename__ = "gather_lot_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planned_meal_id: Mapped[int] = mapped_column(ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False)
    meal_recipe_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False)
    recipe_ingredient_id: Mapped[int] = mapped_column(ForeignKey("recipe_ingredients.id", ondelete="CASCADE"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[int] = mapped_column(ForeignKey("inventory_lots.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "planned_meal_id", "meal_recipe_id", "recipe_ingredient_id", "lot_id",
            name="uq_gather_selection_requirement_lot",
        ),
        CheckConstraint("quantity > 0", name="ck_gather_selection_quantity_positive"),
    )
