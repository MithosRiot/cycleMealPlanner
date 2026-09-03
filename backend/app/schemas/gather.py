from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class GatherSelectionInput(BaseModel):
    lot_id: int
    quantity: Decimal = Field(gt=0)


class GatherRequirementUpdate(BaseModel):
    selections: list[GatherSelectionInput]


class GatherLotRead(BaseModel):
    lot_id: int
    quantity: Decimal
    unit_id: int
    unit_code: str
    location_id: int
    location_name: str | None
    expiration_date: date | None
    opened_date: date | None
    frozen_date: date | None
    thawed_date: date | None


class GatherCandidateRead(GatherLotRead):
    available_quantity: Decimal


class GatherRequirementRead(BaseModel):
    planned_meal_id: int
    meal_name: str
    day_number: int
    slot_label: str
    meal_recipe_id: int
    recipe_id: int
    recipe_ingredient_id: int
    ingredient_id: int
    ingredient_name: str
    required_quantity: Decimal
    unit_id: int
    unit_code: str
    use_date: date | None
    selected_quantity: Decimal
    shortage_quantity: Decimal
    selections: list[GatherLotRead]
    suggestions: list[GatherLotRead]
    candidates: list[GatherCandidateRead]


class GatherCycleRead(BaseModel):
    meal_cycle_id: int
    meal_cycle_name: str
    requirements: list[GatherRequirementRead]


class GatherPickSourceRead(BaseModel):
    planned_meal_id: int
    meal_name: str
    day_number: int
    slot_label: str
    meal_recipe_id: int
    recipe_id: int
    recipe_ingredient_id: int
    ingredient_id: int
    ingredient_name: str
    quantity: Decimal
    unit_id: int
    unit_code: str


class GatherLocationPickRead(BaseModel):
    lot_id: int
    ingredient_id: int
    ingredient_name: str
    quantity: Decimal
    unit_id: int
    unit_code: str
    expiration_date: date | None
    opened_date: date | None
    frozen_date: date | None
    thawed_date: date | None
    sources: list[GatherPickSourceRead]


class GatherLocationGroupRead(BaseModel):
    location_id: int
    location_name: str
    location_path: str
    picks: list[GatherLocationPickRead]


class GatherIncompleteRequirementRead(BaseModel):
    planned_meal_id: int
    meal_name: str
    day_number: int
    slot_label: str
    meal_recipe_id: int
    recipe_id: int
    recipe_ingredient_id: int
    ingredient_id: int
    ingredient_name: str
    required_quantity: Decimal
    selected_quantity: Decimal
    remaining_quantity: Decimal
    unit_id: int
    unit_code: str


class GatherLocationCycleRead(BaseModel):
    meal_cycle_id: int
    meal_cycle_name: str
    complete: bool
    locations: list[GatherLocationGroupRead]
    incomplete_requirements: list[GatherIncompleteRequirementRead]
