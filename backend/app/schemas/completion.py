from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


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
    actual_servings_produced: Decimal | None = None
    actual_servings_eaten: Decimal | None = None
    production_committed_at: datetime | None = None
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


class CompletionOutputPreview(BaseModel):
    component_key: int
    recipe_id: int
    recipe_name: str
    recipe_output_id: int
    output_name: str
    recipe_base_servings: Decimal
    planned_component_servings: Decimal
    base_quantity: Decimal
    calculated_quantity: Decimal
    unit_id: int
    unit_code: str


class CompletionProductionPreview(BaseModel):
    planned_servings: Decimal
    planned_leftover_servings: Decimal
    default_actual_servings_produced: Decimal
    default_actual_servings_eaten: Decimal
    default_leftover_servings: Decimal
    outputs: list[CompletionOutputPreview] = Field(default_factory=list)


class CompletionOutputCommitInput(BaseModel):
    recipe_output_id: int
    component_key: int
    actual_quantity: Decimal = Field(ge=0)
    location_id: int | None = None
    expiration_date: date | None = None
    notes: str | None = None


class CompletionProductionCommitInput(BaseModel):
    actual_servings_produced: Decimal = Field(ge=0)
    actual_servings_eaten: Decimal = Field(ge=0)
    leftover_location_id: int | None = None
    leftover_expiration_date: date | None = None
    leftover_notes: str | None = None
    outputs: list[CompletionOutputCommitInput] = Field(default_factory=list)


class LeftoverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    completion_id: int
    planned_meal_id: int
    source_meal_id: int
    source_meal_name: str
    actual_servings_produced: Decimal
    actual_servings_eaten: Decimal
    leftover_servings: Decimal
    serving_unit: str
    location_id: int | None
    expiration_date: date | None
    notes: str | None
    status: str
    inventory_lot_id: int | None
    inventory_transaction_id: int | None
    created_at: datetime


class CompletionOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    completion_id: int
    component_key: int
    recipe_id: int
    recipe_name: str
    recipe_output_id: int
    output_name: str
    recipe_base_servings: Decimal
    planned_component_servings: Decimal
    base_quantity: Decimal
    calculated_quantity: Decimal
    actual_quantity: Decimal
    quantity_overridden: bool
    unit_id: int
    unit_code: str
    location_id: int | None
    expiration_date: date | None
    notes: str | None
    inventory_lot_id: int | None
    inventory_transaction_id: int | None
    created_at: datetime


class CompletionProductionRead(BaseModel):
    completion: MealCompletionRead
    leftover: LeftoverRead
    outputs: list[CompletionOutputRead] = Field(default_factory=list)
