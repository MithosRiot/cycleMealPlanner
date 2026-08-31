from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AllocationPreviewRequest(BaseModel):
    ingredient_id: int
    quantity: Decimal = Field(gt=0)
    unit_id: int
    use_date: date | None = None
    exclude_cycle_id: int | None = None


class AllocationLotRead(BaseModel):
    lot_id: int
    allocated_quantity: Decimal
    unit_id: int
    unit_code: str
    source_quantity: Decimal
    source_unit_id: int
    source_unit_code: str
    location_id: int
    location_name: str | None
    purchase_date: date | None
    opened_date: date | None
    expiration_date: date | None
    frozen_date: date | None
    thawed_date: date | None


class AllocationPreviewRead(BaseModel):
    ingredient_id: int
    ingredient_name: str | None = None
    requested_quantity: Decimal
    unit_id: int
    unit_code: str
    unit_family: str
    use_date: date | None
    reserved_elsewhere_quantity: Decimal
    allocated_quantity: Decimal
    shortage_quantity: Decimal
    allocations: list[AllocationLotRead]
    planned_meal_id: int | None = None
    meal_name: str | None = None
    day_number: int | None = None
    slot_label: str | None = None
    recipe_id: int | None = None


class CycleAllocationPreviewRead(BaseModel):
    meal_cycle_id: int
    meal_cycle_name: str
    requirements: list[AllocationPreviewRead]
