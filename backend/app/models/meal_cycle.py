from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MealCycle(Base):
    __tablename__ = "meal_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    start_date: Mapped[date | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)

    slot_definitions: Mapped[list[MealSlotDefinition]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        order_by="MealSlotDefinition.sort_order",
    )
    slots: Mapped[list[CycleSlot]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        order_by=lambda: (CycleSlot.day_number, CycleSlot.sort_order),
    )

    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_meal_cycles_household_normalized_name"),
        CheckConstraint("duration_days > 0 AND duration_days <= 365", name="ck_meal_cycles_duration_supported"),
        CheckConstraint("status IN ('DRAFT')", name="ck_meal_cycles_status"),
    )


class MealSlotDefinition(Base):
    __tablename__ = "meal_slot_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cycle: Mapped[MealCycle] = relationship(back_populates="slot_definitions")
    slots: Mapped[list[CycleSlot]] = relationship(back_populates="slot_definition")

    __table_args__ = (
        UniqueConstraint("cycle_id", "sort_order", name="uq_meal_slot_definitions_cycle_sort"),
        CheckConstraint("sort_order >= 0", name="ck_meal_slot_definitions_sort_nonnegative"),
    )


class CycleSlot(Base):
    __tablename__ = "cycle_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False)
    slot_definition_id: Mapped[int] = mapped_column(ForeignKey("meal_slot_definitions.id", ondelete="CASCADE"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[MealCycle] = relationship(back_populates="slots")
    slot_definition: Mapped[MealSlotDefinition] = relationship(back_populates="slots")

    __table_args__ = (
        UniqueConstraint("cycle_id", "day_number", "slot_definition_id", name="uq_cycle_slots_day_definition"),
        CheckConstraint("day_number > 0", name="ck_cycle_slots_day_positive"),
        CheckConstraint("sort_order >= 0", name="ck_cycle_slots_sort_nonnegative"),
    )
