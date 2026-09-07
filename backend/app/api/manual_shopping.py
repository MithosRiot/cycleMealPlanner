from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.meal_cycle import MealCycle
from app.models.reference import InventoryLocation, MeasurementUnit, ShoppingCategory
from app.models.shopping import ManualShoppingItem, ShoppingList
from app.schemas.manual_shopping import (
    ManualShoppingItemComplete,
    ManualShoppingItemRead,
    ManualShoppingItemWrite,
    ManualShoppingListRead,
)

router = APIRouter(prefix="/api/shopping", tags=["shopping"])
HOUSEHOLD_ID = 1


def _cycle_or_404(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(select(MealCycle).where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID))
    if cycle is None:
        raise HTTPException(404, "Meal cycle not found")
    return cycle


def _shopping_list(db: Session, cycle_id: int, *, create: bool) -> ShoppingList | None:
    value = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.meal_cycle_id == cycle_id, ShoppingList.household_id == HOUSEHOLD_ID)
        .options(selectinload(ShoppingList.manual_items))
    )
    if value is None and create:
        value = ShoppingList(household_id=HOUSEHOLD_ID, meal_cycle_id=cycle_id, generated_at=datetime.utcnow())
        db.add(value)
        db.flush()
    return value


def _reload_shopping_list(db: Session, cycle_id: int) -> ShoppingList:
    db.expire_all()
    value = _shopping_list(db, cycle_id, create=False)
    if value is None:
        raise RuntimeError("Manual Shopping list disappeared after commit")
    return value


def _manual_or_404(shopping_list: ShoppingList, item_id: int) -> ManualShoppingItem:
    item = next((row for row in shopping_list.manual_items if row.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Manual Shopping item not found")
    return item


def _validate_refs(db: Session, payload: ManualShoppingItemWrite) -> None:
    if payload.unit_id is not None and db.get(MeasurementUnit, payload.unit_id) is None:
        raise HTTPException(400, "Measurement unit not found")
    if payload.shopping_category_id is not None:
        category = db.scalar(select(ShoppingCategory).where(ShoppingCategory.id == payload.shopping_category_id, ShoppingCategory.household_id == HOUSEHOLD_ID, ShoppingCategory.active.is_(True)))
        if category is None:
            raise HTTPException(400, "Shopping category not found")
    if payload.ingredient_id is not None:
        ingredient = db.scalar(select(Ingredient).where(Ingredient.id == payload.ingredient_id, Ingredient.household_id == HOUSEHOLD_ID, Ingredient.active.is_(True)))
        if ingredient is None:
            raise HTTPException(400, "Ingredient not found")


def _serialize(db: Session, cycle_id: int, shopping_list: ShoppingList | None) -> ManualShoppingListRead:
    if shopping_list is None:
        return ManualShoppingListRead(meal_cycle_id=cycle_id, shopping_list_id=0, items=[])
    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    categories = {row.id: row for row in db.scalars(select(ShoppingCategory).where(ShoppingCategory.household_id == HOUSEHOLD_ID))}
    ingredients = {row.id: row for row in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))}
    locations = {row.id: row for row in db.scalars(select(InventoryLocation).where(InventoryLocation.household_id == HOUSEHOLD_ID))}
    rows: list[ManualShoppingItemRead] = []
    for item in shopping_list.manual_items:
        unit = units.get(item.unit_id) if item.unit_id else None
        category = categories.get(item.shopping_category_id) if item.shopping_category_id else None
        ingredient = ingredients.get(item.ingredient_id) if item.ingredient_id else None
        location = locations.get(item.storage_location_id) if item.storage_location_id else None
        rows.append(ManualShoppingItemRead(
            id=item.id,
            shopping_list_id=shopping_list.id,
            name=item.name,
            quantity=item.quantity,
            unit_id=item.unit_id,
            unit_code=unit.code if unit else None,
            shopping_category_id=item.shopping_category_id,
            shopping_category_name=category.name if category else "Uncategorized",
            shopping_category_sort_order=category.sort_order if category else 9999,
            ingredient_id=item.ingredient_id,
            ingredient_name=ingredient.name if ingredient else None,
            notes=item.notes,
            status=item.status,
            completed_at=item.completed_at,
            inventory_lot_id=item.inventory_lot_id,
            purchase_date=item.purchase_date,
            storage_location_id=item.storage_location_id,
            storage_location_name=location.name if location else None,
            expiration_date=item.expiration_date,
        ))
    rows.sort(key=lambda row: (row.shopping_category_sort_order, row.shopping_category_name.casefold(), row.status != "PENDING", row.name.casefold(), row.id))
    return ManualShoppingListRead(meal_cycle_id=cycle_id, shopping_list_id=shopping_list.id, items=rows)


@router.get("/{cycle_id}/manual-items", response_model=ManualShoppingListRead)
def list_manual_items(cycle_id: int, db: Session = Depends(get_db)) -> ManualShoppingListRead:
    _cycle_or_404(db, cycle_id)
    return _serialize(db, cycle_id, _shopping_list(db, cycle_id, create=False))


@router.post("/{cycle_id}/manual-items", response_model=ManualShoppingListRead, status_code=status.HTTP_201_CREATED)
def create_manual_item(cycle_id: int, payload: ManualShoppingItemWrite, db: Session = Depends(get_db)) -> ManualShoppingListRead:
    _cycle_or_404(db, cycle_id)
    _validate_refs(db, payload)
    shopping_list = _shopping_list(db, cycle_id, create=True)
    assert shopping_list is not None
    shopping_list.manual_items.append(ManualShoppingItem(
        shopping_list_id=shopping_list.id,
        name=payload.name,
        quantity=payload.quantity,
        unit_id=payload.unit_id,
        shopping_category_id=payload.shopping_category_id,
        ingredient_id=payload.ingredient_id,
        notes=payload.notes,
        status="PENDING",
    ))
    db.commit()
    return _serialize(db, cycle_id, _reload_shopping_list(db, cycle_id))


@router.put("/{cycle_id}/manual-items/{item_id}", response_model=ManualShoppingListRead)
def update_manual_item(cycle_id: int, item_id: int, payload: ManualShoppingItemWrite, db: Session = Depends(get_db)) -> ManualShoppingListRead:
    _cycle_or_404(db, cycle_id)
    _validate_refs(db, payload)
    shopping_list = _shopping_list(db, cycle_id, create=False)
    if shopping_list is None:
        raise HTTPException(404, "Shopping list not found")
    item = _manual_or_404(shopping_list, item_id)
    if item.status != "PENDING":
        raise HTTPException(409, "Only pending manual Shopping items can be edited")
    item.name = payload.name
    item.quantity = payload.quantity
    item.unit_id = payload.unit_id
    item.shopping_category_id = payload.shopping_category_id
    item.ingredient_id = payload.ingredient_id
    item.notes = payload.notes
    db.commit()
    return _serialize(db, cycle_id, _reload_shopping_list(db, cycle_id))


@router.delete("/{cycle_id}/manual-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manual_item(cycle_id: int, item_id: int, db: Session = Depends(get_db)) -> Response:
    _cycle_or_404(db, cycle_id)
    shopping_list = _shopping_list(db, cycle_id, create=False)
    if shopping_list is None:
        raise HTTPException(404, "Shopping list not found")
    item = _manual_or_404(shopping_list, item_id)
    if item.status != "PENDING":
        raise HTTPException(409, "Only pending manual Shopping items can be removed")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{cycle_id}/manual-items/{item_id}/complete", response_model=ManualShoppingListRead)
def complete_manual_item(cycle_id: int, item_id: int, payload: ManualShoppingItemComplete, db: Session = Depends(get_db)) -> ManualShoppingListRead:
    _cycle_or_404(db, cycle_id)
    shopping_list = _shopping_list(db, cycle_id, create=False)
    if shopping_list is None:
        raise HTTPException(404, "Shopping list not found")
    item = _manual_or_404(shopping_list, item_id)
    if item.status == "COMPLETED":
        return _serialize(db, cycle_id, shopping_list)
    if item.status != "PENDING":
        raise HTTPException(409, "Only pending manual Shopping items can be completed")

    wants_inventory = payload.inventory_quantity is not None
    if wants_inventory:
        if item.ingredient_id is None:
            raise HTTPException(422, "Link the manual Shopping item to an Ingredient before creating Inventory")
        ingredient = db.scalar(select(Ingredient).where(Ingredient.id == item.ingredient_id, Ingredient.household_id == HOUSEHOLD_ID, Ingredient.active.is_(True)))
        unit = db.get(MeasurementUnit, payload.inventory_unit_id)
        location = db.scalar(select(InventoryLocation).where(InventoryLocation.id == payload.storage_location_id, InventoryLocation.household_id == HOUSEHOLD_ID, InventoryLocation.active.is_(True)))
        if ingredient is None:
            raise HTTPException(400, "Linked Ingredient not found")
        if unit is None:
            raise HTTPException(400, "Inventory measurement unit not found")
        if location is None:
            raise HTTPException(400, "Inventory storage location not found")
        lot = InventoryLot(
            household_id=HOUSEHOLD_ID,
            ingredient_id=item.ingredient_id,
            source_type="INGREDIENT",
            source_id=None,
            source_name=None,
            location_id=location.id,
            quantity=Decimal(payload.inventory_quantity),
            unit_id=unit.id,
            purchase_date=payload.purchase_date,
            opened_date=None,
            expiration_date=payload.expiration_date,
            frozen_date=None,
            thawed_date=None,
            notes=payload.inventory_notes or item.notes,
        )
        db.add(lot)
        db.flush()
        db.add(InventoryTransaction(
            household_id=HOUSEHOLD_ID,
            lot_id=lot.id,
            transaction_type="PURCHASE",
            quantity_delta=Decimal(payload.inventory_quantity),
            unit_id=unit.id,
            from_location_id=None,
            to_location_id=location.id,
            note=f"Manual Shopping item: {item.name}",
        ))
        item.inventory_lot_id = lot.id
        item.purchase_date = payload.purchase_date
        item.storage_location_id = location.id
        item.expiration_date = payload.expiration_date

    item.status = "COMPLETED"
    item.completed_at = datetime.utcnow()
    db.commit()
    return _serialize(db, cycle_id, _reload_shopping_list(db, cycle_id))


@router.post("/{cycle_id}/manual-items/{item_id}/skip", response_model=ManualShoppingListRead)
def skip_manual_item(cycle_id: int, item_id: int, db: Session = Depends(get_db)) -> ManualShoppingListRead:
    _cycle_or_404(db, cycle_id)
    shopping_list = _shopping_list(db, cycle_id, create=False)
    if shopping_list is None:
        raise HTTPException(404, "Shopping list not found")
    item = _manual_or_404(shopping_list, item_id)
    if item.status == "SKIPPED":
        return _serialize(db, cycle_id, shopping_list)
    if item.status != "PENDING":
        raise HTTPException(409, "Only pending manual Shopping items can be skipped")
    item.status = "SKIPPED"
    item.completed_at = datetime.utcnow()
    db.commit()
    return _serialize(db, cycle_id, _reload_shopping_list(db, cycle_id))
