from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IngredientAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    shopping_category_id: int | None = None
    preferred_unit_id: int | None = None
    default_location_id: int | None = None
    perishable: bool = False
    staple_enabled: bool = False
    staple_minimum: Decimal | None = Field(default=None, ge=0)
    staple_target: Decimal | None = Field(default=None, ge=0)
    staple_unit_id: int | None = None
    notes: str | None = None
    aliases: list[str] = Field(default_factory=list)


class IngredientUpdate(IngredientCreate):
    active: bool = True


class IngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    name: str
    shopping_category_id: int | None
    preferred_unit_id: int | None
    default_location_id: int | None
    perishable: bool
    staple_enabled: bool
    staple_minimum: Decimal | None
    staple_target: Decimal | None
    staple_unit_id: int | None
    active: bool
    notes: str | None
    aliases: list[IngredientAliasRead]


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(default="CUSTOM", min_length=1, max_length=30)


class TagUpdate(TagCreate):
    active: bool = True


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    name: str
    category: str
    active: bool
