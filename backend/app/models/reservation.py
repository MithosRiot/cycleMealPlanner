from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False)
    planned_meal_id: Mapped[int] = mapped_column(ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False)
    meal_recipe_id: Mapped[int | None] = mapped_column(Integer)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False)
    recipe_ingredient_id: Mapped[int | None] = mapped_column(Integer)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_reservations_quantity_nonnegative"),
        CheckConstraint("status IN ('ACTIVE','RELEASED')", name="ck_inventory_reservations_status"),
        UniqueConstraint(
            "planned_meal_id",
            "meal_recipe_id",
            "recipe_ingredient_id",
            name="uq_inventory_reservations_source",
        ),
    )
