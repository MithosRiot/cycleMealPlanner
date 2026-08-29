from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ShoppingItemAdjustment(BaseModel):
    adjustment_quantity: Decimal


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


class ShoppingListRead(BaseModel):
    id: int
    meal_cycle_id: int
    meal_cycle_name: str
    generated_at: datetime
    items: list[ShoppingListItemRead]
