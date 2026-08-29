from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PlannedMealAssign(BaseModel):
    meal_id: int


class PlannedMealMove(BaseModel):
    target_cycle_slot_id: int


class PlannedMealLock(BaseModel):
    locked: bool


class PlannedMealPlanningUpdate(BaseModel):
    planned_servings: Decimal = Field(gt=0)
    planned_leftover_servings: Decimal = Field(ge=0)
    component_serving_overrides: dict[int, Decimal] = Field(default_factory=dict)


class PlannedMealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_slot_id: int
    meal_id: int
    locked: bool
    planned_servings: Decimal
    planned_leftover_servings: Decimal
    component_serving_overrides: str
    scaled_components: str
    snapshot_name: str
    snapshot_description: str | None
    snapshot_meal_types: str
    snapshot_components: str


class RandomFillResult(BaseModel):
    filled_count: int
