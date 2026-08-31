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
