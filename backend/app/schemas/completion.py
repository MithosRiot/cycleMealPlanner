from decimal import Decimal
from pydantic import BaseModel, Field


class CompletionUsageUpdate(BaseModel):
    usage_id: int
    actual_ingredient_id: int
    actual_quantity: Decimal = Field(ge=0)
    actual_unit_id: int
    notes: str | None = None


class CompletionDraftUpdate(BaseModel):
    usages: list[CompletionUsageUpdate] = Field(default_factory=list)


class CompletionSubstitutionSuggestion(BaseModel):
    ingredient_id: int
    ingredient_name: str
    ratio: Decimal
    preferred: bool
    notes: str | None


class CompletionUsageRead(BaseModel):
    id: int
    component_key: int
    recipe_id: int
    recipe_name: str
    recipe_ingredient_id: int
    planned_ingredient_id: int
    planned_ingredient_name: str
    planned_quantity: Decimal
    planned_unit_id: int
    planned_unit_code: str
    actual_ingredient_id: int
    actual_ingredient_name: str
    actual_quantity: Decimal
    actual_unit_id: int
    actual_unit_code: str
    preparation: str | None
    prep_method: str | None
    prep_size: str | None
    prep_state: str | None
    notes: str | None
    substitutions: list[CompletionSubstitutionSuggestion]


class MealCompletionRead(BaseModel):
    id: int
    planned_meal_id: int
    status: str
    meal_name: str
    snapshot_planned_servings: Decimal
    snapshot_planned_leftover_servings: Decimal
    stale: bool
    usages: list[CompletionUsageRead]
