from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("4"))

    __table_args__ = (CheckConstraint("default_servings > 0", name="ck_households_default_servings_positive"),)


class MeasurementUnit(Base):
    __tablename__ = "measurement_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    unit_family: Mapped[str] = mapped_column(String(20), nullable=False)
    base_multiplier: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    allows_fraction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (CheckConstraint("base_multiplier > 0", name="ck_units_multiplier_positive"),)


class ShoppingCategory(Base):
    __tablename__ = "shopping_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("household_id", "name", name="uq_shopping_categories_household_name"),
        CheckConstraint("sort_order >= 0", name="ck_shopping_categories_sort_order"),
    )


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    parent_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location_type: Mapped[str] = mapped_column(String(30), nullable=False, default="OTHER")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped[InventoryLocation | None] = relationship(remote_side="InventoryLocation.id", back_populates="children")
    children: Mapped[list[InventoryLocation]] = relationship(back_populates="parent")

    __table_args__ = (
        UniqueConstraint("household_id", "parent_location_id", "name", name="uq_inventory_locations_sibling_name"),
        CheckConstraint("sort_order >= 0", name="ck_inventory_locations_sort_order"),
    )
