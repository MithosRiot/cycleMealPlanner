from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Leftover(Base):
    __tablename__ = "leftovers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completion_id: Mapped[int] = mapped_column(ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False, unique=True)
    planned_meal_id: Mapped[int] = mapped_column(ForeignKey("planned_meals.id", ondelete="RESTRICT"), nullable=False)
    source_meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="RESTRICT"), nullable=False)
    source_meal_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_components: Mapped[str] = mapped_column(Text, nullable=False)
    actual_servings_produced: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    actual_servings_eaten: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    leftover_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    serving_unit: Mapped[str] = mapped_column(String(40), nullable=False, default="serving")
    location_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_locations.id", ondelete="RESTRICT"))
    expiration_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE")
    inventory_lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"), unique=True)
    inventory_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("actual_servings_produced >= 0", name="ck_leftovers_produced_nonnegative"),
        CheckConstraint("actual_servings_eaten >= 0", name="ck_leftovers_eaten_nonnegative"),
        CheckConstraint("actual_servings_eaten <= actual_servings_produced", name="ck_leftovers_eaten_not_over_produced"),
        CheckConstraint("leftover_servings >= 0", name="ck_leftovers_quantity_nonnegative"),
        CheckConstraint("status IN ('NONE','AVAILABLE')", name="ck_leftovers_status"),
    )


class MealCompletionOutput(Base):
    __tablename__ = "meal_completion_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completion_id: Mapped[int] = mapped_column(ForeignKey("meal_completions.id", ondelete="CASCADE"), nullable=False)
    component_key: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipe_output_id: Mapped[int] = mapped_column(ForeignKey("recipe_outputs.id", ondelete="RESTRICT"), nullable=False)
    output_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipe_base_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    planned_component_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    calculated_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    quantity_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(30), nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_locations.id", ondelete="RESTRICT"))
    expiration_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    inventory_lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"), unique=True)
    inventory_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_transactions.id", ondelete="RESTRICT"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("completion_id", "component_key", "recipe_output_id", name="uq_meal_completion_outputs_source"),
        CheckConstraint("recipe_base_servings > 0", name="ck_meal_completion_outputs_base_servings_positive"),
        CheckConstraint("planned_component_servings >= 0", name="ck_meal_completion_outputs_component_servings_nonnegative"),
        CheckConstraint("base_quantity >= 0", name="ck_meal_completion_outputs_base_quantity_nonnegative"),
        CheckConstraint("calculated_quantity >= 0", name="ck_meal_completion_outputs_calculated_nonnegative"),
        CheckConstraint("actual_quantity >= 0", name="ck_meal_completion_outputs_actual_nonnegative"),
    )
