from decimal import Decimal

from pydantic import BaseModel, Field


class CookingTimerInput(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    duration_seconds: int = Field(gt=0)
    notes: str | None = None
    sort_order: int = Field(default=0, ge=0)


class CookingTemperatureInput(BaseModel):
    label: str = Field(default="temperature", min_length=1, max_length=80)
    value: Decimal
    unit: str = Field(pattern="^(F|C)$")
    notes: str | None = None
    sort_order: int = Field(default=0, ge=0)


class CookingStepInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    instructions: str | None = None
    prep_group_id: int | None = None
    sort_order: int = Field(default=0, ge=0)
    timers: list[CookingTimerInput] = Field(default_factory=list)
    recipe_equipment_ids: list[int] = Field(default_factory=list)
    temperatures: list[CookingTemperatureInput] = Field(default_factory=list)


class CookingTimerRead(BaseModel):
    id: int
    cooking_step_id: int
    label: str
    duration_seconds: int
    notes: str | None
    sort_order: int


class CookingEquipmentContext(BaseModel):
    recipe_equipment_id: int
    equipment_id: int
    equipment_name: str
    quantity: int
    notes: str | None
    sort_order: int


class CookingTemperatureRead(BaseModel):
    id: int
    cooking_step_id: int
    label: str
    value: Decimal
    unit: str
    notes: str | None
    sort_order: int


class CookingStepRead(BaseModel):
    id: int
    recipe_id: int
    prep_group_id: int | None
    prep_group_name: str | None
    title: str
    instructions: str | None
    sort_order: int
    timers: list[CookingTimerRead]
    equipment: list[CookingEquipmentContext]
    temperatures: list[CookingTemperatureRead]


class CookingIngredientContext(BaseModel):
    ingredient_id: int
    ingredient_name: str
    quantity: Decimal
    unit_id: int
    unit_code: str
    preparation: str | None = None
    prep_method: str | None = None
    prep_size: str | None = None
    prep_state: str | None = None


class CookingTimerRuntime(BaseModel):
    timer_id: int
    label: str
    duration_seconds: int
    notes: str | None
    sort_order: int
    status: str
    remaining_seconds: int
    ends_at_epoch: int | None


class CookingModeStep(BaseModel):
    step_id: int
    component_index: int
    meal_recipe_id: int
    recipe_id: int
    recipe_name: str
    title: str
    instructions: str | None
    prep_group_id: int | None
    prep_group_name: str | None
    step_number: int
    total_steps: int
    ingredients: list[CookingIngredientContext]
    timers: list[CookingTimerRuntime]
    equipment: list[CookingEquipmentContext]
    temperatures: list[CookingTemperatureRead]


class CookingModeMeal(BaseModel):
    planned_meal_id: int
    day_number: int
    slot_label: str
    meal_name: str
    planned_servings: Decimal
    planned_leftover_servings: Decimal
    steps: list[CookingModeStep]
    components_without_steps: list[str]


class CycleCookingModeResponse(BaseModel):
    cycle_id: int
    meals: list[CookingModeMeal]


class CookingTimerAction(BaseModel):
    action: str = Field(pattern="^(START|PAUSE|RESUME|RESET|DISMISS)$")
