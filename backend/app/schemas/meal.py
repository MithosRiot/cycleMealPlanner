from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingredient import TagRead


class MealRecipeInput(BaseModel):
    recipe_id: int
    serving_multiplier: Decimal = Field(default=Decimal("1"), gt=0)
    default_servings: Decimal | None = Field(default=None, gt=0)
    sort_order: int = Field(default=0, ge=0)
    notes: str | None = None


class MealRecipeRead(MealRecipeInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meal_id: int


class MealBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    favorite: bool = False
    meal_types: list[str] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)
    recipes: list[MealRecipeInput] = Field(min_length=1)


class MealCreate(MealBase):
    pass


class MealUpdate(MealBase):
    active: bool = True


class MealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    name: str
    description: str | None
    favorite: bool
    active: bool
    meal_types: list[str]
    tags: list[TagRead]
    recipes: list[MealRecipeRead]
