from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MealCompletion(Base):
    __tablename__ = "meal_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planned_meal_id: Mapped[int] = mapped_column(ForeignKey("planned_meals.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    plan_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_planned_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    snapshot_planned_leftover_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    snapshot_scaled_components: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    usages: Mapped[list[MealCompletionUsage]] = relationship(
        back_populates="completion",
        cascade="all, delete-orphan",
        order_by="MealCompletionUsage.id",
    )

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','FINALIZED')", name="ck_meal_completions_status"),
    )


class MealCompletionUsage(Base):
    __tablename__ = "meal_completion_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completion_id: Mapped[int] = mapped_column(ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False)
    component_key: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipe_ingredient_id: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    planned_ingredient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    planned_unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    planned_unit_code: Mapped[str] = mapped_column(String(30), nullable=False)
    actual_ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    actual_ingredient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    actual_unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    actual_unit_code: Mapped[str] = mapped_column(String(30), nullable=False)
    preparation: Mapped[str | None] = mapped_column(String(160))
    prep_method: Mapped[str | None] = mapped_column(String(80))
    prep_size: Mapped[str | None] = mapped_column(String(80))
    prep_state: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)

    completion: Mapped[MealCompletion] = relationship(back_populates="usages")

    __table_args__ = (
        UniqueConstraint("completion_id", "component_key", "recipe_ingredient_id", name="uq_meal_completion_usage_source"),
        CheckConstraint("planned_quantity >= 0", name="ck_meal_completion_usage_planned_nonnegative"),
        CheckConstraint("actual_quantity >= 0", name="ck_meal_completion_usage_actual_nonnegative"),
    )
