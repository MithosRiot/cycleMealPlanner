from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.shopping import _regenerate
from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.meal_cycle import MealCycle
from app.models.reference import InventoryLocation, MeasurementUnit
from app.models.shopping import ShoppingList
from app.schemas.inventory import (
    CorrectionAction,
    DiscardAction,
    FreezeAction,
    InventoryLotCreate,
    InventoryLotDetail,
    InventoryLotMetadataUpdate,
    InventoryLotRead,
    InventorySplitRead,
    QuantityAction,
    SplitAction,
    TransferAction,
)
from app.services.inventory_availability import availability_for
from app.services.production_coverage import reserved_for_lot

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


def _reserved_produced_quantity(db: Session, lot: InventoryLot) -> Decimal:
    if lot.source_type not in {"LEFTOVER", "RECIPE_OUTPUT"}:
        return Decimal("0")
    return reserved_for_lot(db, lot.id)


def _ensure_reservation_capacity(db: Session, lot: InventoryLot, target_quantity: Decimal) -> None:
    current = Decimal(lot.quantity)
    if target_quantity >= current:
        return

    if lot.source_type in {"LEFTOVER", "RECIPE_OUTPUT"}:
        reserved = _reserved_produced_quantity(db, lot)
        if target_quantity < reserved:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot reduce produced stock below its reserved future coverage ({reserved})",
            )
        return

    if lot.source_type == "INGREDIENT" and lot.ingredient_id is not None:
        unit = db.get(MeasurementUnit, lot.unit_id)
        if unit is None:
            raise HTTPException(status_code=409, detail="Inventory lot measurement unit no longer exists")
        physical, reserved, _, _ = availability_for(db, lot.ingredient_id, unit.unit_family, unit)
        projected_physical = physical - (current - target_quantity)
        if projected_physical < reserved:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot reduce Ingredient stock below active reservations: "
                    f"{reserved} {unit.code} reserved; {projected_physical} {unit.code} would remain"
                ),
            )


def _record(
    db: Session,
    lot: InventoryLot,
    transaction_type: str,
    delta: Decimal,
    note: str | None = None,
    from_location_id: int | None = None,
    to_location_id: int | None = None,
    reason: str | None = None,
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
            reason=reason.strip() if reason else None,
            note=note.strip() if note else None,
        )
    )


def _refresh_active_shopping(db: Session) -> None:
    db.flush()
    cycles = list(db.scalars(select(MealCycle).where(
        MealCycle.household_id == DEFAULT_HOUSEHOLD_ID,
        MealCycle.status == "ACTIVE",
    )))
    for cycle in cycles:
        shopping_list_id = db.scalar(select(ShoppingList.id).where(ShoppingList.meal_cycle_id == cycle.id))
        if shopping_list_id is not None:
            _regenerate(db, cycle, commit=False)


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
        source_type="INGREDIENT",
        source_id=None,
        source_name=None,
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
def update_inventory_metadata(lot_id: int, payload: InventoryLotMetadataUpdate, db: Session = Depends(get_db)) -> InventoryLot:
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
    target = current - quantity
    _ensure_reservation_capacity(db, lot, target)
    lot.quantity = target
    _record(db, lot, "MANUAL_REMOVE", -quantity, payload.note)
    db.commit()
    db.refresh(lot)
    return lot


def _discard_inventory(lot_id: int, payload: DiscardAction, transaction_type: str, db: Session) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    quantity = Decimal(payload.quantity)
    current = Decimal(lot.quantity)
    if quantity > current:
        raise HTTPException(status_code=409, detail="Inventory quantity cannot become negative")
    target = current - quantity
    _ensure_reservation_capacity(db, lot, target)
    lot.quantity = target
    _record(db, lot, transaction_type, -quantity, payload.note, reason=payload.reason)
    _refresh_active_shopping(db)
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/waste", response_model=InventoryLotRead)
def waste_inventory(lot_id: int, payload: DiscardAction, db: Session = Depends(get_db)) -> InventoryLot:
    return _discard_inventory(lot_id, payload, "WASTE", db)


@router.post("/{lot_id}/spoilage", response_model=InventoryLotRead)
def spoil_inventory(lot_id: int, payload: DiscardAction, db: Session = Depends(get_db)) -> InventoryLot:
    return _discard_inventory(lot_id, payload, "SPOILAGE", db)


@router.post("/{lot_id}/correct", response_model=InventoryLotRead)
def correct_inventory(lot_id: int, payload: CorrectionAction, db: Session = Depends(get_db)) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    target = Decimal(payload.quantity)
    _ensure_reservation_capacity(db, lot, target)
    delta = target - Decimal(lot.quantity)
    lot.quantity = target
    _record(db, lot, "CORRECTION", delta, payload.note)
    db.commit()
    db.refresh(lot)
    return lot


@router.post("/{lot_id}/freeze", response_model=InventoryLotRead)
def freeze_inventory(lot_id: int, payload: FreezeAction, db: Session = Depends(get_db)) -> InventoryLot:
    lot = _lot_or_404(db, lot_id)
    if lot.frozen_date is not None and lot.thawed_date is None:
        raise HTTPException(status_code=409, detail="Inventory lot is already frozen")
    if lot.source_type == "INGREDIENT":
        ingredient = db.get(Ingredient, lot.ingredient_id) if lot.ingredient_id is not None else None
        if ingredient is None or not ingredient.perishable:
            raise HTTPException(status_code=409, detail="This Ingredient lot is not eligible for a freeze resolution")

    location = db.get(InventoryLocation, payload.freezer_location_id)
    if (
        location is None
        or location.household_id != DEFAULT_HOUSEHOLD_ID
        or not location.active
        or location.location_type != "FREEZER"
    ):
        raise HTTPException(status_code=400, detail="Selected location is not an active Freezer")

    old_location = lot.location_id
    lot.location_id = location.id
    lot.frozen_date = date.today()
    lot.thawed_date = None
    note = payload.note.strip() if payload.note else "Expiration resolution: frozen"
    _record(db, lot, "TRANSFER", Decimal("0"), note, old_location, location.id)
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
    if _reserved_produced_quantity(db, source) > 0:
        raise HTTPException(status_code=409, detail="Reserved produced stock cannot be split until its future coverage is released")

    target_location = db.get(InventoryLocation, payload.to_location_id)
    if target_location is None or target_location.household_id != DEFAULT_HOUSEHOLD_ID or not target_location.active:
        raise HTTPException(status_code=400, detail="Inventory location not found")

    source.quantity = current - quantity
    child = InventoryLot(
        household_id=source.household_id,
        ingredient_id=source.ingredient_id,
        source_type=source.source_type,
        source_id=source.source_id,
        source_name=source.source_name,
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
    return {"source": _lot_or_404(db, source_id), "child": _lot_or_404(db, child_id)}
