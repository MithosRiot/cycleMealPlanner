from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.reference import InventoryLocation, MeasurementUnit
from app.schemas.inventory import (
    CorrectionAction,
    InventoryLotCreate,
    InventoryLotDetail,
    InventoryLotMetadataUpdate,
    InventoryLotRead,
    InventorySplitRead,
    QuantityAction,
    SplitAction,
    TransferAction,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])
DEFAULT_HOUSEHOLD_ID = 1


def _lot_or_404(db: Session, lot_id: int) -> InventoryLot:
    lot = db.scalar(
        select(InventoryLot)
        .options(selectinload(InventoryLot.transactions))
        .where(InventoryLot.id == lot_id, InventoryLot.household_id == DEFAULT_HOUSEHOLD_ID)
    )
    if lot is None:
        raise HTTPException(status_code=404, detail="Inventory lot not found")
    return lot


def _validate_refs(db: Session, ingredient_id: int, location_id: int, unit_id: int) -> None:
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.household_id != DEFAULT_HOUSEHOLD_ID or not ingredient.active:
        raise HTTPException(status_code=400, detail="Ingredient not found")
    location = db.get(InventoryLocation, location_id)
    if location is None or location.household_id != DEFAULT_HOUSEHOLD_ID or not location.active:
        raise HTTPException(status_code=400, detail="Inventory location not found")
    if db.get(MeasurementUnit, unit_id) is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")


def _record(
    db: Session,
    lot: InventoryLot,
    transaction_type: str,
    delta: Decimal,
    note: str | None = None,
    from_location_id: int | None = None,
    to_location_id: int | None = None,
) -> None:
    db.add(
        InventoryTransaction(
            household_id=DEFAULT_HOUSEHOLD_ID,
            lot_id=lot.id,
            transaction_type=transaction_type,
            quantity_delta=delta,
            unit_id=lot.unit_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            note=note.strip() if note else None,
        )
    )


@router.get("", response_model=list[InventoryLotRead])
def list_inventory(
    ingredient_id: int | None = None,
    location_id: int | None = None,
    include_empty: bool = False,
    db: Session = Depends(get_db),
) -> list[InventoryLot]:
    statement = select(InventoryLot).where(InventoryLot.household_id == DEFAULT_HOUSEHOLD_ID)
    if ingredient_id is not None:
        statement = statement.where(InventoryLot.ingredient_id == ingredient_id)
    if location_id is not None:
        statement = statement.where(InventoryLot.location_id == location_id)
    if not include_empty:
        statement = statement.where(InventoryLot.quantity > 0)
    return list(db.scalars(statement.order_by(InventoryLot.expiration_date, InventoryLot.id)))


@router.get("/{lot_id}", response_model=InventoryLotDetail)
def get_inventory_lot(lot_id: int, db: Session = Depends(get_db)) -> InventoryLot:
    return _lot_or_404(db, lot_id)


@router.post("", response_model=InventoryLotRead, status_code=status.HTTP_201_CREATED)
def create_inventory_lot(payload: InventoryLotCreate, db: Session = Depends(get_db)) -> InventoryLot:
    _validate_refs(db, payload.ingredient_id, payload.location_id, payload.unit_id)
    lot = InventoryLot(
        household_id=DEFAULT_HOUSEHOLD_ID,
        ingredient_id=payload.ingredient_id,
        location_id=payload.location_id,
        quantity=payload.quantity,
        unit_id=payload.unit_id,
        purchase_date=payload.purchase_date,
        opened_date=payload.opened_date,
        expiration_date=payload.expiration_date,
        frozen_date=payload.frozen_date,
        thawed_date=payload.thawed_date,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(lot)
    db.flush()
    _record(db, lot, payload.transaction_type, Decimal(payload.quantity), payload.notes)
    db.commit()
    db.refresh(lot)
    return lot


@router.put("/{lot_id}", response_model=InventoryLotRead)
def update_inventory_metadata(
    lot_id: int,
    payload: InventoryLotMetadataUpdate,
    db: Session = Depends(get_db),
) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    lot.purchase_date = payload.purchase_date
    lot.opened_date = payload.opened_date
    lot.expiration_date = payload.expiration_date
    lot.frozen_date = payload.frozen_date
    lot.thawed_date = payload.thawed_date
    lot.notes = payload.notes.strip() if payload.notes else None
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/add", response_model=InventoryLotRead)
def add_inventory(lot_id: int, payload: QuantityAction, db: Session = Depends(get_db)) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    lot.quantity = Decimal(lot.quantity) + Decimal(payload.quantity)
    _record(db, lot, "MANUAL_ADD", Decimal(payload.quantity), payload.note)
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/remove", response_model=InventoryLotRead)
def remove_inventory(lot_id: int, payload: QuantityAction, db: Session = Depends(get_db)) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    quantity = Decimal(payload.quantity)
    current = Decimal(lot.quantity)
    if quantity > current:
        raise HTTPException(status_code=409, detail="Inventory quantity cannot become negative")
    lot.quantity = current - quantity
    _record(db, lot, "MANUAL_REMOVE", -quantity, payload.note)
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/correct", response_model=InventoryLotRead)
def correct_inventory(lot_id: int, payload: CorrectionAction, db: Session = Depends(get_db)) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    target = Decimal(payload.quantity)
    delta = target - Decimal(lot.quantity)
    lot.quantity = target
    _record(db, lot, "CORRECTION", delta, payload.note)
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/transfer", response_model=InventoryLotRead)
def transfer_inventory(lot_id: int, payload: TransferAction, db: Session = Depends(get_db)) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    location = db.get(InventoryLocation, payload.to_location_id)
    if location is None or location.household_id != DEFAULT_HOUSEHOLD_ID or not location.active:
        raise HTTPException(status_code=400, detail="Inventory location not found")
    old_location = lot.location_id
    if old_location == payload.to_location_id:
        return lot
    lot.location_id = payload.to_location_id
    _record(db, lot, "TRANSFER", Decimal("0"), payload.note, old_location, payload.to_location_id)
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/split", response_model=InventorySplitRead, status_code=status.HTTP_201_CREATED)
def split_inventory(lot_id: int, payload: SplitAction, db: Session = Depends(get_db)) -> dict:
    source = _lot_or_404(db, lot_id)
    quantity = Decimal(payload.quantity)
    current = Decimal(source.quantity)
    if quantity >= current:
        raise HTTPException(status_code=409, detail="Split quantity must be less than the source lot quantity; use Transfer to move the whole lot")

    target_location = db.get(InventoryLocation, payload.to_location_id)
    if target_location is None or target_location.household_id != DEFAULT_HOUSEHOLD_ID or not target_location.active:
        raise HTTPException(status_code=400, detail="Inventory location not found")

    source.quantity = current - quantity
    child = InventoryLot(
        household_id=source.household_id,
        ingredient_id=source.ingredient_id,
        location_id=payload.to_location_id,
        quantity=quantity,
        unit_id=source.unit_id,
        purchase_date=source.purchase_date,
        opened_date=source.opened_date,
        expiration_date=source.expiration_date,
        frozen_date=source.frozen_date,
        thawed_date=source.thawed_date,
        notes=source.notes,
    )
    db.add(child)
    db.flush()

    user_note = payload.note.strip() if payload.note else None
    source_note = f"Split {quantity} to lot #{child.id}" + (f" — {user_note}" if user_note else "")
    child_note = f"Split {quantity} from lot #{source.id}" + (f" — {user_note}" if user_note else "")
    _record(db, source, "TRANSFER", -quantity, source_note, source.location_id, payload.to_location_id)
    _record(db, child, "TRANSFER", quantity, child_note, source.location_id, payload.to_location_id)

    source_id = source.id
    child_id = child.id
    db.commit()
    db.expire_all()
    return {
        "source": _lot_or_404(db, source_id),
        "child": _lot_or_404(db, child_id),
    }
