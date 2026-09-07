from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MealHistoryAllocation(BaseModel):
    lot_id: int
    inventory_transaction_id: int
    source_quantity: Decimal
    source_unit_code: str


class MealHistoryUsage(BaseModel):
    recipe_name: str
    planned_ingredient_name: str
    planned_quantity: Decimal
    planned_unit_code: str
    actual_ingredient_name: str
    actual_quantity: Decimal
    actual_unit_code: str
    substituted: bool
    notes: str | None = None
    allocations: list[MealHistoryAllocation] = Field(default_factory=list)


class MealHistoryLeftover(BaseModel):
    id: int
    leftover_servings: Decimal
    serving_unit: str
    expiration_date: date | None
    notes: str | None
    inventory_lot_id: int | None
    created_at: datetime


class MealHistoryOutput(BaseModel):
    id: int
    recipe_name: str
    output_name: str
    actual_quantity: Decimal
    unit_code: str
    quantity_overridden: bool
    expiration_date: date | None
    notes: str | None
    inventory_lot_id: int | None
    created_at: datetime


class MealHistoryEntry(BaseModel):
    completion_id: int
    planned_meal_id: int
    meal_name: str
    finalized_at: datetime
    production_committed_at: datetime | None
    planned_servings: Decimal
    planned_leftover_servings: Decimal
    actual_servings_produced: Decimal | None
    actual_servings_eaten: Decimal | None
    usages: list[MealHistoryUsage] = Field(default_factory=list)
    leftover: MealHistoryLeftover | None = None
    outputs: list[MealHistoryOutput] = Field(default_factory=list)


class InventoryHistoryEntry(BaseModel):
    transaction_id: int
    created_at: datetime
    transaction_type: str
    lot_id: int
    ingredient_id: int | None
    ingredient_name: str | None
    source_type: str
    source_id: int | None
    source_name: str | None
    quantity_delta: Decimal
    unit_id: int
    unit_code: str
    from_location_id: int | None
    from_location_name: str | None
    to_location_id: int | None
    to_location_name: str | None
    reason: str | None
    note: str | None
