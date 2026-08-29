from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.ingredient import Tag


recipe_tags = Table(
    "recipe_tags",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    serving_unit: Mapped[str] = mapped_column(String(40), nullable=False, default="servings")
    yield_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    yield_unit_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_units.id", ondelete="SET NULL"))
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.sort_order",
    )
    meal_types: Mapped[list[RecipeMealType]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeMealType.meal_type",
    )
    tags: Mapped[list[Tag]] = relationship(secondary=recipe_tags)

    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_recipes_household_normalized_name"),
        CheckConstraint("base_servings > 0", name="ck_recipes_base_servings_positive"),
        CheckConstraint("yield_quantity IS NULL OR yield_quantity > 0", name="ck_recipes_yield_quantity_positive"),
        CheckConstraint("prep_time_minutes IS NULL OR prep_time_minutes >= 0", name="ck_recipes_prep_time_nonnegative"),
        CheckConstraint("cook_time_minutes IS NULL OR cook_time_minutes >= 0", name="ck_recipes_cook_time_nonnegative"),
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    display_text: Mapped[str | None] = mapped_column(String(160))
    preparation: Mapped[str | None] = mapped_column(String(160))
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scaling_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="LINEAR")
    required_state: Mapped[str] = mapped_column(String(30), nullable=False, default="ANY")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_recipe_ingredients_quantity_nonnegative"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_ingredients_sort_order_nonnegative"),
        CheckConstraint(
            "scaling_mode IN ('LINEAR','FIXED','ROUND_UP','MANUAL')",
            name="ck_recipe_ingredients_scaling_mode",
        ),
    )


class RecipeMealType(Base):
    __tablename__ = "recipe_meal_types"

    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True)
    meal_type: Mapped[str] = mapped_column(String(30), primary_key=True)

    recipe: Mapped[Recipe] = relationship(back_populates="meal_types")
