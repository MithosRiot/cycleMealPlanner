from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RecipeOutputInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    quantity: Decimal = Field(gt=0)
    unit_id: int
    notes: str | None = None
    active: bool = True
    sort_order: int = Field(default=0, ge=0)


class RecipeOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    name: str
    quantity: Decimal
    unit_id: int
    notes: str | None
    active: bool
    sort_order: int


class RecipeDependencyInput(BaseModel):
    recipe_output_id: int
    quantity: Decimal = Field(gt=0)
    unit_id: int
    scaling_mode: str = Field(default="LINEAR", pattern="^(LINEAR|FIXED|ROUND_UP|MANUAL)$")
    notes: str | None = None
    sort_order: int = Field(default=0, ge=0)


class RecipeDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    recipe_output_id: int
    quantity: Decimal
    unit_id: int
    scaling_mode: str
    notes: str | None
    sort_order: int


class RecipeOutputBundle(BaseModel):
    outputs: list[RecipeOutputRead]
    dependencies: list[RecipeDependencyRead]


class DependencyScaleRequest(BaseModel):
    requested_servings: Decimal = Field(gt=0)


class ScaledDependencyRead(BaseModel):
    dependency_id: int
    recipe_output_id: int
    source_recipe_id: int
    output_name: str
    quantity: Decimal
    unit_id: int
    unit_code: str
    scaling_mode: str
    manual_review: bool


class DependencyScaleResponse(BaseModel):
    recipe_id: int
    requested_servings: Decimal
    dependencies: list[ScaledDependencyRead]
