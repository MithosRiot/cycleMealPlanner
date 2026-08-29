from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HouseholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    default_servings: Decimal


class HouseholdUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    default_servings: Decimal = Field(gt=0)


class MeasurementUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    unit_family: str
    base_multiplier: Decimal
    allows_fraction: bool


class ShoppingCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(default=0, ge=0)


class ShoppingCategoryUpdate(ShoppingCategoryCreate):
    active: bool = True


class ShoppingCategoryRead(ShoppingCategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    active: bool


class InventoryLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_location_id: int | None = None
    location_type: str = Field(default="OTHER", min_length=1, max_length=30)
    sort_order: int = Field(default=0, ge=0)


class InventoryLocationUpdate(InventoryLocationCreate):
    active: bool = True


class InventoryLocationRead(InventoryLocationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    active: bool


class UnitConversionRequest(BaseModel):
    quantity: Decimal
    from_unit_code: str
    to_unit_code: str


class UnitConversionResponse(BaseModel):
    quantity: Decimal
    unit_code: str
