from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.ingredient import Tag


meal_tags = Table(
    "meal_tags",
    Base.metadata,
    Column("meal_id", ForeignKey("meals.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
)


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    recipes: Mapped[list[MealRecipe]] = relationship(
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealRecipe.sort_order",
    )
    meal_types: Mapped[list[MealMealType]] = relationship(
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealMealType.meal_type",
    )
    tags: Mapped[list[Tag]] = relationship(secondary=meal_tags)

    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_meals_household_normalized_name"),
    )


class MealRecipe(Base):
    __tablename__ = "meal_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"), nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False)
    serving_multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("1"))
    default_servings: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    meal: Mapped[Meal] = relationship(back_populates="recipes")

    __table_args__ = (
        CheckConstraint("serving_multiplier > 0", name="ck_meal_recipes_serving_multiplier_positive"),
        CheckConstraint("default_servings IS NULL OR default_servings > 0", name="ck_meal_recipes_default_servings_positive"),
        CheckConstraint("sort_order >= 0", name="ck_meal_recipes_sort_order_nonnegative"),
    )


class MealMealType(Base):
    __tablename__ = "meal_meal_types"

    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"), primary_key=True)
    meal_type: Mapped[str] = mapped_column(String(30), primary_key=True)

    meal: Mapped[Meal] = relationship(back_populates="meal_types")
