from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ShoppingItemAdjustment(BaseModel):
    adjustment_quantity: Decimal


class ShoppingItemComplete(BaseModel):
    actual_quantity: Decimal = Field(gt=0)
    actual_unit_id: int
    storage_location_id: int
    purchase_date: date | None = None
    expiration_date: date | None = None
    notes: str | None = None


class ShoppingListItemRead(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    shopping_category_id: int | None
    shopping_category_name: str
    shopping_category_sort_order: int
    unit_id: int
    unit_code: str
    unit_family: str
    required_quantity: Decimal
    inventory_quantity: Decimal
    generated_quantity: Decimal
    adjustment_quantity: Decimal
    final_quantity: Decimal
    source_trace: str
    warning: str | None
    status: str
    actual_quantity: Decimal | None
    actual_unit_id: int | None
    actual_unit_code: str | None
    purchase_date: date | None
    storage_location_id: int | None
    expiration_date: date | None
    purchase_notes: str | None
    inventory_lot_id: int | None
    completed_at: datetime | None


class ShoppingListRead(BaseModel):
    id: int
    meal_cycle_id: int
    meal_cycle_name: str
    generated_at: datetime
    items: list[ShoppingListItemRead]
