from pydantic import BaseModel, ConfigDict, Field


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="OTHER", min_length=1, max_length=80)
    notes: str | None = None


class EquipmentUpdate(EquipmentCreate):
    active: bool = True


class EquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: int
    name: str
    category: str
    notes: str | None
    active: bool
