from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.reference import Household, InventoryLocation, MeasurementUnit, ShoppingCategory
from app.schemas.reference import (
    HouseholdRead,
    HouseholdUpdate,
    InventoryLocationCreate,
    InventoryLocationRead,
    InventoryLocationUpdate,
    MeasurementUnitRead,
    ShoppingCategoryCreate,
    ShoppingCategoryRead,
    ShoppingCategoryUpdate,
    UnitConversionRequest,
    UnitConversionResponse,
)
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/reference", tags=["reference"])
DEFAULT_HOUSEHOLD_ID = 1


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A conflicting record already exists") from exc


def _validate_parent(db: Session, parent_id: int | None, location_id: int | None = None) -> None:
    if parent_id is None:
        return
    if location_id is not None and parent_id == location_id:
        raise HTTPException(status_code=400, detail="A location cannot be its own parent")

    current = db.get(InventoryLocation, parent_id)
    if current is None or current.household_id != DEFAULT_HOUSEHOLD_ID or not current.active:
        raise HTTPException(status_code=400, detail="Parent inventory location not found")

    while current.parent_location_id is not None:
        if location_id is not None and current.parent_location_id == location_id:
            raise HTTPException(status_code=400, detail="Location hierarchy cannot contain a cycle")
        current = db.get(InventoryLocation, current.parent_location_id)
        if current is None:
            break


@router.get("/household", response_model=HouseholdRead)
def get_household(db: Session = Depends(get_db)) -> Household:
    household = db.get(Household, DEFAULT_HOUSEHOLD_ID)
    if household is None:
        raise HTTPException(status_code=404, detail="Default household not found")
    return household


@router.put("/household", response_model=HouseholdRead)
def update_household(payload: HouseholdUpdate, db: Session = Depends(get_db)) -> Household:
    household = db.get(Household, DEFAULT_HOUSEHOLD_ID)
    if household is None:
        raise HTTPException(status_code=404, detail="Default household not found")
    household.name = payload.name.strip()
    household.default_servings = payload.default_servings
    _commit(db)
    db.refresh(household)
    return household


@router.get("/units", response_model=list[MeasurementUnitRead])
def list_units(db: Session = Depends(get_db)) -> list[MeasurementUnit]:
    return list(db.scalars(select(MeasurementUnit).order_by(MeasurementUnit.unit_family, MeasurementUnit.code)))


@router.post("/units/convert", response_model=UnitConversionResponse)
def convert_units(payload: UnitConversionRequest, db: Session = Depends(get_db)) -> UnitConversionResponse:
    from_unit = db.scalar(select(MeasurementUnit).where(MeasurementUnit.code == payload.from_unit_code))
    to_unit = db.scalar(select(MeasurementUnit).where(MeasurementUnit.code == payload.to_unit_code))
    if from_unit is None or to_unit is None:
        raise HTTPException(status_code=404, detail="Measurement unit not found")
    try:
        converted = convert_quantity(Decimal(payload.quantity), from_unit, to_unit)
    except UnitConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UnitConversionResponse(quantity=converted, unit_code=to_unit.code)


@router.get("/shopping-categories", response_model=list[ShoppingCategoryRead])
def list_shopping_categories(db: Session = Depends(get_db)) -> list[ShoppingCategory]:
    statement = select(ShoppingCategory).where(
        ShoppingCategory.household_id == DEFAULT_HOUSEHOLD_ID,
        ShoppingCategory.active.is_(True),
    ).order_by(ShoppingCategory.sort_order, ShoppingCategory.name)
    return list(db.scalars(statement))


@router.post("/shopping-categories", response_model=ShoppingCategoryRead, status_code=status.HTTP_201_CREATED)
def create_shopping_category(payload: ShoppingCategoryCreate, db: Session = Depends(get_db)) -> ShoppingCategory:
    category = ShoppingCategory(
        household_id=DEFAULT_HOUSEHOLD_ID,
        name=payload.name.strip(),
        sort_order=payload.sort_order,
    )
    db.add(category)
    _commit(db)
    db.refresh(category)
    return category


@router.put("/shopping-categories/{category_id}", response_model=ShoppingCategoryRead)
def update_shopping_category(
    category_id: int, payload: ShoppingCategoryUpdate, db: Session = Depends(get_db)
) -> ShoppingCategory:
    category = db.get(ShoppingCategory, category_id)
    if category is None or category.household_id != DEFAULT_HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Shopping category not found")
    category.name = payload.name.strip()
    category.sort_order = payload.sort_order
    category.active = payload.active
    _commit(db)
    db.refresh(category)
    return category


@router.delete("/shopping-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_shopping_category(category_id: int, db: Session = Depends(get_db)) -> Response:
    category = db.get(ShoppingCategory, category_id)
    if category is None or category.household_id != DEFAULT_HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Shopping category not found")
    category.active = False
    _commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/inventory-locations", response_model=list[InventoryLocationRead])
def list_inventory_locations(db: Session = Depends(get_db)) -> list[InventoryLocation]:
    statement = select(InventoryLocation).where(
        InventoryLocation.household_id == DEFAULT_HOUSEHOLD_ID,
        InventoryLocation.active.is_(True),
    ).order_by(InventoryLocation.sort_order, InventoryLocation.name)
    return list(db.scalars(statement))


@router.post("/inventory-locations", response_model=InventoryLocationRead, status_code=status.HTTP_201_CREATED)
def create_inventory_location(payload: InventoryLocationCreate, db: Session = Depends(get_db)) -> InventoryLocation:
    _validate_parent(db, payload.parent_location_id)
    location = InventoryLocation(
        household_id=DEFAULT_HOUSEHOLD_ID,
        parent_location_id=payload.parent_location_id,
        name=payload.name.strip(),
        location_type=payload.location_type.upper(),
        sort_order=payload.sort_order,
    )
    db.add(location)
    _commit(db)
    db.refresh(location)
    return location


@router.put("/inventory-locations/{location_id}", response_model=InventoryLocationRead)
def update_inventory_location(
    location_id: int, payload: InventoryLocationUpdate, db: Session = Depends(get_db)
) -> InventoryLocation:
    location = db.get(InventoryLocation, location_id)
    if location is None or location.household_id != DEFAULT_HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Inventory location not found")
    _validate_parent(db, payload.parent_location_id, location_id)
    location.name = payload.name.strip()
    location.parent_location_id = payload.parent_location_id
    location.location_type = payload.location_type.upper()
    location.sort_order = payload.sort_order
    location.active = payload.active
    _commit(db)
    db.refresh(location)
    return location


@router.delete("/inventory-locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_inventory_location(location_id: int, db: Session = Depends(get_db)) -> Response:
    location = db.get(InventoryLocation, location_id)
    if location is None or location.household_id != DEFAULT_HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Inventory location not found")
    active_child = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.parent_location_id == location_id,
            InventoryLocation.active.is_(True),
        )
    )
    if active_child is not None:
        raise HTTPException(status_code=409, detail="Archive child locations first")
    location.active = False
    _commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
