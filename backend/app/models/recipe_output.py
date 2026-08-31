from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RecipeOutput(Base):
    __tablename__ = "recipe_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("recipe_id", "normalized_name", name="uq_recipe_outputs_recipe_normalized_name"),
        CheckConstraint("quantity > 0", name="ck_recipe_outputs_quantity_positive"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_outputs_sort_order_nonnegative"),
    )


class RecipeDependency(Base):
    __tablename__ = "recipe_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    recipe_output_id: Mapped[int] = mapped_column(ForeignKey("recipe_outputs.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    scaling_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="LINEAR")
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("recipe_id", "recipe_output_id", name="uq_recipe_dependencies_recipe_output"),
        CheckConstraint("quantity > 0", name="ck_recipe_dependencies_quantity_positive"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_dependencies_sort_order_nonnegative"),
        CheckConstraint("scaling_mode IN ('LINEAR','FIXED','ROUND_UP','MANUAL')", name="ck_recipe_dependencies_scaling_mode"),
    )
