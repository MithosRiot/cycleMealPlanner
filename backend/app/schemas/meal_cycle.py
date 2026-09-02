from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.planned_meal import PlannedMealRead


class MealSlotDefinitionInput(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(ge=0)
    serving_time: time | None = None


class MealCycleInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    duration_days: int = Field(gt=0, le=365)
    start_date: date | None = None
    notes: str | None = None
    slot_definitions: list[MealSlotDefinitionInput] = Field(min_length=1)


class MealCycleScheduleUpdate(BaseModel):
    start_date: date | None = None
    serving_times: dict[int, time | None] = Field(default_factory=dict)


class SlotPopulationRule(BaseModel):
    include_meal_ids: list[int] = Field(default_factory=list)
    exclude_meal_ids: list[int] = Field(default_factory=list)


class PopulationRulesUpdate(BaseModel):
    include_meal_ids: list[int] = Field(default_factory=list)
    exclude_meal_ids: list[int] = Field(default_factory=list)
    slot_rules: dict[str, SlotPopulationRule] = Field(default_factory=dict)


class SmartPlanningPreferencesUpdate(BaseModel):
    repeat_spacing_days: int = Field(default=0, ge=0, le=365)
    favorite_boost: float = Field(default=1.0, ge=1.0, le=10.0)
    history_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    tag_weights: dict[int, float] = Field(default_factory=dict)


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
    scheduled_date: date | None = None
    serving_time: time | None = None
    scheduled_datetime: datetime | None = None
    planned_meal: PlannedMealRead | None = None


class MealCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    name: str
    duration_days: int
    status: str
    start_date: date | None
    notes: str | None
    population_rules: str
    smart_preferences: str
    slot_definitions: list[MealSlotDefinitionRead]
    slots: list[CycleSlotRead]
