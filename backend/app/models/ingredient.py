from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    shopping_category_id: Mapped[int | None] = mapped_column(ForeignKey("shopping_categories.id", ondelete="SET NULL"))
    preferred_unit_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_units.id", ondelete="SET NULL"))
    default_location_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_locations.id", ondelete="SET NULL"))
    perishable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staple_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staple_minimum: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    staple_target: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    staple_unit_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_units.id", ondelete="SET NULL"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    aliases: Mapped[list[IngredientAlias]] = relationship(back_populates="ingredient", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_ingredients_household_normalized_name"),
        CheckConstraint("staple_minimum IS NULL OR staple_minimum >= 0", name="ck_ingredients_staple_minimum_nonnegative"),
        CheckConstraint("staple_target IS NULL OR staple_target >= 0", name="ck_ingredients_staple_target_nonnegative"),
        CheckConstraint(
            "staple_minimum IS NULL OR staple_target IS NULL OR staple_target >= staple_minimum",
            name="ck_ingredients_staple_target_gte_minimum",
        ),
    )


class IngredientAlias(Base):
    __tablename__ = "ingredient_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(120), nullable=False)

    ingredient: Mapped[Ingredient] = relationship(back_populates="aliases")

    __table_args__ = (UniqueConstraint("ingredient_id", "normalized_alias", name="uq_ingredient_alias_normalized"),)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="CUSTOM")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("household_id", "normalized_name", name="uq_tags_household_normalized_name"),)
