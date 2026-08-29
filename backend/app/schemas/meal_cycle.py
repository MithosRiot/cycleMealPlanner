from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MealSlotDefinitionInput(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(ge=0)


class MealCycleInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    duration_days: int = Field(gt=0, le=365)
    start_date: date | None = None
    notes: str | None = None
    slot_definitions: list[MealSlotDefinitionInput] = Field(min_length=1)


class MealSlotDefinitionRead(MealSlotDefinitionInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int


class CycleSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    slot_definition_id: int
    day_number: int
    sort_order: int


class MealCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    name: str
    duration_days: int
    status: str
    start_date: date | None
    notes: str | None
    slot_definitions: list[MealSlotDefinitionRead]
    slots: list[CycleSlotRead]
