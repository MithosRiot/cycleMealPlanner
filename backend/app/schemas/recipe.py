from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingredient import TagRead


class RecipePrepGroupInput(BaseModel):
    client_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    sort_order: int = Field(default=0, ge=0)


class RecipePrepGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    name: str
    sort_order: int


class RecipeAdvancePrepInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    lead_time_minutes: int = Field(ge=0)
    duration_minutes: int | None = Field(default=None, ge=0)
    instructions: str | None = None
    prep_group_key: str | None = Field(default=None, max_length=80)
    sort_order: int = Field(default=0, ge=0)


class RecipeAdvancePrepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    prep_group_id: int | None
    title: str
    lead_time_minutes: int
    duration_minutes: int | None
    instructions: str | None
    sort_order: int


class RecipeIngredientInput(BaseModel):
    ingredient_id: int
    prep_group_key: str | None = Field(default=None, max_length=80)
    quantity: Decimal = Field(ge=0)
    unit_id: int
    display_text: str | None = Field(default=None, max_length=160)
    preparation: str | None = Field(default=None, max_length=160)
    prep_method: str | None = Field(default=None, max_length=80)
    prep_size: str | None = Field(default=None, max_length=80)
    prep_state: str | None = Field(default=None, max_length=80)
    optional: bool = False
    scaling_mode: str = Field(default="LINEAR", pattern="^(LINEAR|FIXED|ROUND_UP|MANUAL)$")
    required_state: str = Field(default="ANY", max_length=30)
    sort_order: int = Field(default=0, ge=0)
    notes: str | None = None


class RecipeIngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    ingredient_id: int
    prep_group_id: int | None
    quantity: Decimal
    unit_id: int
    display_text: str | None
    preparation: str | None
    prep_method: str | None
    prep_size: str | None
    prep_state: str | None
    optional: bool
    scaling_mode: str
    required_state: str
    sort_order: int
    notes: str | None


class RecipeBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    base_servings: Decimal = Field(gt=0)
    serving_unit: str = Field(default="servings", min_length=1, max_length=40)
    yield_quantity: Decimal | None = Field(default=None, gt=0)
    yield_unit_id: int | None = None
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None
    favorite: bool = False
    meal_types: list[str] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)
    prep_groups: list[RecipePrepGroupInput] = Field(default_factory=list)
    advance_prep: list[RecipeAdvancePrepInput] = Field(default_factory=list)
    ingredients: list[RecipeIngredientInput] = Field(default_factory=list)


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(RecipeBase):
    active: bool = True


class RecipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: int
    name: str
    description: str | None
    base_servings: Decimal
    serving_unit: str
    yield_quantity: Decimal | None
    yield_unit_id: int | None
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    notes: str | None
    favorite: bool
    active: bool
    meal_types: list[str]
    tags: list[TagRead]
    prep_groups: list[RecipePrepGroupRead]
    advance_prep: list[RecipeAdvancePrepRead]
    ingredients: list[RecipeIngredientRead]


class RecipeScaleRequest(BaseModel):
    requested_servings: Decimal = Field(gt=0)
    unit_overrides: dict[int, str] = Field(default_factory=dict)


class ScaledIngredientRead(BaseModel):
    recipe_ingredient_id: int
    ingredient_id: int
    prep_group_id: int | None
    quantity: Decimal
    unit_id: int
    unit_code: str
    scaling_mode: str
    manual_review: bool
    preparation: str | None
    prep_method: str | None
    prep_size: str | None
    prep_state: str | None


class RecipeScaleResponse(BaseModel):
    recipe_id: int
    base_servings: Decimal
    requested_servings: Decimal
    scale_factor: Decimal
    ingredients: list[ScaledIngredientRead]
