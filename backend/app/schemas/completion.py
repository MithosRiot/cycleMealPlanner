from datetime import datetime
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


class CompletionAllocationRead(BaseModel):
    id: int
    usage_id: int
    lot_id: int
    inventory_transaction_id: int
    quantity: Decimal
    unit_id: int
    unit_code: str
    source_quantity: Decimal
    source_unit_id: int
    source_unit_code: str


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
    allocations: list[CompletionAllocationRead] = Field(default_factory=list)


class MealCompletionRead(BaseModel):
    id: int
    planned_meal_id: int
    status: str
    meal_name: str
    snapshot_planned_servings: Decimal
    snapshot_planned_leftover_servings: Decimal
    stale: bool
    finalized_at: datetime | None = None
    usages: list[CompletionUsageRead]


class CompletionShortageRead(BaseModel):
    usage_id: int
    ingredient_id: int
    ingredient_name: str
    requested_quantity: Decimal
    unit_id: int
    unit_code: str
    shortage_quantity: Decimal


class CompletionFinalizeResponse(BaseModel):
    completion: MealCompletionRead | None = None
    shortages: list[CompletionShortageRead] = Field(default_factory=list)
