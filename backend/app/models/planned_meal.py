from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PlannedMeal(Base):
    __tablename__ = "planned_meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_slot_id: Mapped[int] = mapped_column(ForeignKey("cycle_slots.id", ondelete="CASCADE"), nullable=False, unique=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="RESTRICT"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="SAVED_MEAL")
    source_origin_planned_meal_id: Mapped[int | None] = mapped_column(Integer)
    source_record_id: Mapped[int | None] = mapped_column(Integer)
    source_recipe_output_id: Mapped[int | None] = mapped_column(Integer)
    source_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    source_unit_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"))
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    planned_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("4"))
    planned_leftover_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("0"))
    component_serving_overrides: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scaled_components: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    snapshot_name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_description: Mapped[str | None] = mapped_column(Text)
    snapshot_meal_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    snapshot_components: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    cycle_slot = relationship("CycleSlot", back_populates="planned_meal")

    @property
    def scheduled_date(self) -> date | None:
        return self.cycle_slot.scheduled_date

    @property
    def serving_time(self) -> time | None:
        return self.cycle_slot.serving_time

    @property
    def scheduled_datetime(self) -> datetime | None:
        return self.cycle_slot.scheduled_datetime

    __table_args__ = (
        CheckConstraint("planned_servings > 0", name="ck_planned_meals_servings_positive"),
        CheckConstraint("planned_leftover_servings >= 0", name="ck_planned_meals_leftovers_nonnegative"),
    )
