from decimal import Decimal

from pydantic import BaseModel, Field


class CookingStepInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    instructions: str | None = None
    prep_group_id: int | None = None
    sort_order: int = Field(default=0, ge=0)


class CookingStepRead(BaseModel):
    id: int
    recipe_id: int
    prep_group_id: int | None
    prep_group_name: str | None
    title: str
    instructions: str | None
    sort_order: int


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
