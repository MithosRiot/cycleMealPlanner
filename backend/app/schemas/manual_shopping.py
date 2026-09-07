from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class ManualShoppingItemWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    quantity: Decimal = Field(gt=0)
    unit_id: int | None = None
    shopping_category_id: int | None = None
    ingredient_id: int | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Manual Shopping item name cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ManualShoppingItemComplete(BaseModel):
    inventory_quantity: Decimal | None = Field(default=None, gt=0)
    inventory_unit_id: int | None = None
    storage_location_id: int | None = None
    purchase_date: date | None = None
    expiration_date: date | None = None
    inventory_notes: str | None = None

    @field_validator("inventory_notes")
    @classmethod
    def _clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _intake_is_all_or_none(self):
        values = (self.inventory_quantity, self.inventory_unit_id, self.storage_location_id)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("Inventory intake requires quantity, unit, and storage location")
        return self


class ManualShoppingItemRead(BaseModel):
    id: int
    shopping_list_id: int
    name: str
    quantity: Decimal
    unit_id: int | None
    unit_code: str | None
    shopping_category_id: int | None
    shopping_category_name: str
    shopping_category_sort_order: int
    ingredient_id: int | None
    ingredient_name: str | None
    notes: str | None
    status: str
    completed_at: datetime | None
    inventory_lot_id: int | None
    purchase_date: date | None
    storage_location_id: int | None
    storage_location_name: str | None
    expiration_date: date | None


class ManualShoppingListRead(BaseModel):
    meal_cycle_id: int
    shopping_list_id: int
    items: list[ManualShoppingItemRead]
