from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RecipeCookingTimer(Base):
    __tablename__ = "recipe_cooking_timers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cooking_step_id: Mapped[int] = mapped_column(ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="ck_recipe_cooking_timers_duration_positive"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_cooking_timers_sort_order_nonnegative"),
    )


class PlannedCookingTimer(Base):
    __tablename__ = "planned_cooking_timers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planned_meal_id: Mapped[int] = mapped_column(ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False)
    cooking_timer_id: Mapped[int] = mapped_column(ForeignKey("recipe_cooking_timers.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="READY")
    remaining_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    ends_at_epoch: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("planned_meal_id", "cooking_timer_id", name="uq_planned_cooking_timers_meal_timer"),
        CheckConstraint("status IN ('READY','RUNNING','PAUSED','COMPLETED','DISMISSED')", name="ck_planned_cooking_timers_status"),
        CheckConstraint("remaining_seconds >= 0", name="ck_planned_cooking_timers_remaining_nonnegative"),
    )
