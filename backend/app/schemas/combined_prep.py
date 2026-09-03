from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CombinedPrepSourceRead(BaseModel):
    planned_meal_id: int
    meal_recipe_id: int
    recipe_id: int
    recipe_name: str
    recipe_ingredient_id: int | None = None
    advance_prep_id: int | None = None
    quantity: Decimal | None = None
    unit_code: str | None = None


class CombinedIngredientPrepRead(BaseModel):
    planned_meal_id: int
    meal_name: str
    day_number: int
    slot_label: str
    ingredient_id: int
    ingredient_name: str
    prep_group_name: str | None
    preparation: str | None
    prep_method: str | None
    prep_size: str | None
    prep_state: str | None
    quantity: Decimal
    unit_id: int
    unit_code: str
    sources: list[CombinedPrepSourceRead]


class CombinedAdvancePrepRead(BaseModel):
    planned_meal_id: int
    meal_name: str
    day_number: int
    slot_label: str
    task_type: str
    title: str
    instructions: str | None
    prep_group_name: str | None
    lead_time_minutes: int
    duration_minutes: int | None
    serving_datetime: datetime | None
    start_datetime: datetime | None
    end_datetime: datetime | None
    reminder_enabled: bool
    reminder_offset_minutes: int | None
    reminder_at: datetime | None
    sources: list[CombinedPrepSourceRead]


class CombinedPrepRead(BaseModel):
    meal_cycle_id: int
    meal_cycle_name: str
    ingredient_prep: list[CombinedIngredientPrepRead]
    advance_prep: list[CombinedAdvancePrepRead]
