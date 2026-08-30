from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.equipment import Equipment
from app.schemas.equipment import EquipmentCreate, EquipmentRead, EquipmentUpdate
from app.services.normalization import normalize_name

router = APIRouter(prefix="/api/equipment", tags=["equipment"])
HOUSEHOLD_ID = 1


def _equipment_or_404(db: Session, equipment_id: int) -> Equipment:
    item = db.scalar(select(Equipment).where(Equipment.id == equipment_id, Equipment.household_id == HOUSEHOLD_ID))
    if item is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return item


def _save(db: Session, item: Equipment, payload: EquipmentCreate | EquipmentUpdate) -> Equipment:
    normalized = normalize_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Equipment name cannot be blank")
    existing = select(Equipment.id).where(Equipment.household_id == HOUSEHOLD_ID, Equipment.normalized_name == normalized)
    if item.id is not None:
        existing = existing.where(Equipment.id != item.id)
    if db.scalar(existing) is not None:
        raise HTTPException(status_code=409, detail="Equipment name already exists")

    item.name = payload.name.strip()
    item.normalized_name = normalized
    item.category = payload.category.strip().upper()
    item.notes = payload.notes.strip() if payload.notes else None
    if isinstance(payload, EquipmentUpdate):
        item.active = payload.active
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Equipment could not be saved") from exc
    db.refresh(item)
    return item


@router.get("", response_model=list[EquipmentRead])
def list_equipment(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[Equipment]:
    statement = select(Equipment).where(Equipment.household_id == HOUSEHOLD_ID)
    if not include_inactive:
        statement = statement.where(Equipment.active.is_(True))
    return list(db.scalars(statement.order_by(Equipment.name)))


@router.post("", response_model=EquipmentRead, status_code=status.HTTP_201_CREATED)
def create_equipment(payload: EquipmentCreate, db: Session = Depends(get_db)) -> Equipment:
    return _save(db, Equipment(household_id=HOUSEHOLD_ID, name=payload.name.strip(), normalized_name=normalize_name(payload.name)), payload)


@router.put("/{equipment_id}", response_model=EquipmentRead)
def update_equipment(equipment_id: int, payload: EquipmentUpdate, db: Session = Depends(get_db)) -> Equipment:
    return _save(db, _equipment_or_404(db, equipment_id), payload)


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_equipment(equipment_id: int, db: Session = Depends(get_db)) -> None:
    item = _equipment_or_404(db, equipment_id)
    item.active = False
    db.commit()
