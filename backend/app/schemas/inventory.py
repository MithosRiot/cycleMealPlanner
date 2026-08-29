from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InventoryLotCreate(BaseModel):
    ingredient_id: int
    location_id: int
    quantity: Decimal = Field(gt=0)
    unit_id: int
    purchase_date: date | None = None
    opened_date: date | None = None
    expiration_date: date | None = None
    frozen_date: date | None = None
    thawed_date: date | None = None
    notes: str | None = None
    transaction_type: str = Field(default="MANUAL_ADD", pattern="^(PURCHASE|MANUAL_ADD)$")


class InventoryLotMetadataUpdate(BaseModel):
    purchase_date: date | None = None
    opened_date: date | None = None
    expiration_date: date | None = None
    frozen_date: date | None = None
    thawed_date: date | None = None
    notes: str | None = None


class QuantityAction(BaseModel):
    quantity: Decimal = Field(gt=0)
    note: str | None = None


class CorrectionAction(BaseModel):
    quantity: Decimal = Field(ge=0)
    note: str | None = None


class TransferAction(BaseModel):
    to_location_id: int
    note: str | None = None


class InventoryTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lot_id: int
    transaction_type: str
    quantity_delta: Decimal
    unit_id: int
    from_location_id: int | None
    to_location_id: int | None
    note: str | None
    created_at: datetime


class InventoryLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    ingredient_id: int
    location_id: int
    quantity: Decimal
    unit_id: int
    purchase_date: date | None
    opened_date: date | None
    expiration_date: date | None
    frozen_date: date | None
    thawed_date: date | None
    notes: str | None


class InventoryLotDetail(InventoryLotRead):
    transactions: list[InventoryTransactionRead]
