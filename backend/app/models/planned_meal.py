from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PlannedMeal(Base):
    __tablename__ = "planned_meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_slot_id: Mapped[int] = mapped_column(ForeignKey("cycle_slots.id", ondelete="CASCADE"), nullable=False, unique=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="RESTRICT"), nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snapshot_name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_description: Mapped[str | None] = mapped_column(Text)
    snapshot_meal_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    snapshot_components: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    cycle_slot = relationship("CycleSlot", back_populates="planned_meal")
