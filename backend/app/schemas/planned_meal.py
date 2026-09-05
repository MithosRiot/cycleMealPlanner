from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlannedMealAssign(BaseModel):
    meal_id: int


class DirectRecipeAssign(BaseModel):
    recipe_id: int
    planned_servings: Decimal = Field(gt=0)
    planned_leftover_servings: Decimal = Field(default=Decimal("0"), ge=0)


class ProducedSourceAssign(BaseModel):
    source_type: str = Field(pattern="^(LEFTOVER|RECIPE_OUTPUT)$")
    source_origin_planned_meal_id: int
    source_record_id: int | None = None
    source_recipe_output_id: int | None = None
    quantity: Decimal = Field(gt=0)
    unit_id: int

    @model_validator(mode="after")
    def validate_output_identity(self):
        if self.source_type == "RECIPE_OUTPUT" and self.source_record_id is None and self.source_recipe_output_id is None:
            raise ValueError("Recipe output placement requires a produced record or RecipeOutput id")
        return self


class ProducedSourceOption(BaseModel):
    source_type: str
    source_origin_planned_meal_id: int
    source_record_id: int | None
    source_recipe_output_id: int | None
    source_name: str
    source_meal_id: int | None
    unit_id: int
    unit_code: str
    planned_quantity: Decimal
    physical_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    lot_id: int | None
    expiration_date: date | None


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
    meal_id: int | None
    source_type: str = "SAVED_MEAL"
    source_recipe_id: int | None = None
    source_origin_planned_meal_id: int | None = None
    source_record_id: int | None = None
    source_recipe_output_id: int | None = None
    source_quantity: Decimal | None = None
    source_unit_id: int | None = None
    locked: bool
    planned_servings: Decimal
    planned_leftover_servings: Decimal
    component_serving_overrides: str
    scaled_components: str
    snapshot_name: str
    snapshot_description: str | None
    snapshot_meal_types: str
    snapshot_components: str
    scheduled_date: date | None = None
    serving_time: time | None = None
    scheduled_datetime: datetime | None = None


class RandomFillResult(BaseModel):
    filled_count: int
