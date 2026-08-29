from pydantic import BaseModel, ConfigDict


class PlannedMealAssign(BaseModel):
    meal_id: int


class PlannedMealMove(BaseModel):
    target_cycle_slot_id: int


class PlannedMealLock(BaseModel):
    locked: bool


class PlannedMealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_slot_id: int
    meal_id: int
    locked: bool
    snapshot_name: str
    snapshot_description: str | None
    snapshot_meal_types: str
    snapshot_components: str


class RandomFillResult(BaseModel):
    filled_count: int
