from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PlannedMeal(Base):
    __tablename__ = "planned_meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_slot_id: Mapped[int] = mapped_column(ForeignKey("cycle_slots.id", ondelete="CASCADE"), nullable=False, unique=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="RESTRICT"), nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    planned_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("4"))
    planned_leftover_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("0"))
    component_serving_overrides: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    snapshot_name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_description: Mapped[str | None] = mapped_column(Text)
    snapshot_meal_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    snapshot_components: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    cycle_slot = relationship("CycleSlot", back_populates="planned_meal")

    __table_args__ = (
        CheckConstraint("planned_servings > 0", name="ck_planned_meals_servings_positive"),
        CheckConstraint("planned_leftover_servings >= 0", name="ck_planned_meals_leftovers_nonnegative"),
    )
