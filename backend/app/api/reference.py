from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.reference import Household, InventoryLocation, MeasurementUnit, ShoppingCategory
from app.schemas.reference import (
    HouseholdRead,
    HouseholdUpdate,
    InventoryLocationCreate,
    InventoryLocationRead,
    MeasurementUnitRead,
    ShoppingCategoryCreate,
    ShoppingCategoryRead,
    UnitConversionRequest,
    UnitConversionResponse,
)
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/reference", tags=["reference"])
DEFAULT_HOUSEHOLD_ID = 1


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
    db.commit()
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
    db.commit()
    db.refresh(category)
    return category


@router.get("/inventory-locations", response_model=list[InventoryLocationRead])
def list_inventory_locations(db: Session = Depends(get_db)) -> list[InventoryLocation]:
    statement = select(InventoryLocation).where(
        InventoryLocation.household_id == DEFAULT_HOUSEHOLD_ID,
        InventoryLocation.active.is_(True),
    ).order_by(InventoryLocation.sort_order, InventoryLocation.name)
    return list(db.scalars(statement))


@router.post("/inventory-locations", response_model=InventoryLocationRead, status_code=status.HTTP_201_CREATED)
def create_inventory_location(payload: InventoryLocationCreate, db: Session = Depends(get_db)) -> InventoryLocation:
    if payload.parent_location_id is not None:
        parent = db.get(InventoryLocation, payload.parent_location_id)
        if parent is None or parent.household_id != DEFAULT_HOUSEHOLD_ID:
            raise HTTPException(status_code=400, detail="Parent inventory location not found")

    location = InventoryLocation(
        household_id=DEFAULT_HOUSEHOLD_ID,
        parent_location_id=payload.parent_location_id,
        name=payload.name.strip(),
        location_type=payload.location_type.upper(),
        sort_order=payload.sort_order,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location
