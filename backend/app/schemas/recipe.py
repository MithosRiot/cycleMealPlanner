from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingredient import TagRead


class RecipeIngredientInput(BaseModel):
    ingredient_id: int
    quantity: Decimal = Field(ge=0)
    unit_id: int
    display_text: str | None = Field(default=None, max_length=160)
    preparation: str | None = Field(default=None, max_length=160)
    optional: bool = False
    scaling_mode: str = Field(default="LINEAR", pattern="^(LINEAR|FIXED|ROUND_UP|MANUAL)$")
    required_state: str = Field(default="ANY", max_length=30)
    sort_order: int = Field(default=0, ge=0)
    notes: str | None = None


class RecipeIngredientRead(RecipeIngredientInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: int


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
    ingredients: list[RecipeIngredientRead]


class RecipeScaleRequest(BaseModel):
    requested_servings: Decimal = Field(gt=0)
    unit_overrides: dict[int, str] = Field(default_factory=dict)


class ScaledIngredientRead(BaseModel):
    recipe_ingredient_id: int
    ingredient_id: int
    quantity: Decimal
    unit_id: int
    unit_code: str
    scaling_mode: str
    manual_review: bool


class RecipeScaleResponse(BaseModel):
    recipe_id: int
    base_servings: Decimal
    requested_servings: Decimal
    scale_factor: Decimal
    ingredients: list[ScaledIngredientRead]
