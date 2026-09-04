from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InventoryReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    planned_meal_id: int
    meal_recipe_id: int | None
    recipe_id: int
    recipe_ingredient_id: int | None
    ingredient_id: int
    quantity: Decimal
    unit_id: int
    status: str


class ReservationCycleSummary(BaseModel):
    cycle_id: int
    active_count: int
    released_count: int
    reservations: list[InventoryReservationRead]


class InventoryAvailabilityRead(BaseModel):
    ingredient_id: int
    unit_family: str
    unit_id: int
    unit_code: str
    physical_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    shortage_quantity: Decimal


class ProductionCoverageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    planned_meal_id: int
    cycle_slot_id: int
    source_origin_planned_meal_id: int
    source_type: str
    source_record_id: int | None
    source_recipe_output_id: int | None
    lot_id: int | None
    requested_quantity: Decimal
    reserved_quantity: Decimal
    shortage_quantity: Decimal
    unit_id: int
    status: str
    release_reason: str | None
    created_at: datetime
    updated_at: datetime
    released_at: datetime | None


class ProductionCoverageCycleSummary(BaseModel):
    cycle_id: int
    active_count: int
    released_count: int
    shortage_count: int
    reservations: list[ProductionCoverageRead]


class ProductionAvailabilityRead(BaseModel):
    lot_id: int
    source_type: str
    source_id: int | None
    source_name: str | None
    unit_id: int
    physical_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    expiration_date: date | None
