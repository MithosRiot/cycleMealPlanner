import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.reference import InventoryLocation, MeasurementUnit, ShoppingCategory
from app.models.shopping import ShoppingList, ShoppingListItem
from app.schemas.shopping import ShoppingItemAdjustment, ShoppingItemComplete, ShoppingListRead
from app.services.units import convert_quantity

router = APIRouter(prefix="/api/shopping", tags=["shopping"])
HOUSEHOLD_ID = 1
TERMINAL_STATUSES = {"COMPLETED", "SKIPPED"}


def _cycle_or_404(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _shopping_list_or_404(db: Session, cycle_id: int) -> ShoppingList:
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.meal_cycle_id == cycle_id, ShoppingList.household_id == HOUSEHOLD_ID)
        .options(selectinload(ShoppingList.items))
    )
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list has not been generated")
    return shopping_list


def _item_or_404(shopping_list: ShoppingList, item_id: int) -> ShoppingListItem:
    item = next((value for value in shopping_list.items if value.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Shopping list item not found")
    return item


def _serialize(db: Session, shopping_list: ShoppingList, cycle: MealCycle) -> dict:
    ingredients = {
        ingredient.id: ingredient
        for ingredient in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    categories = {category.id: category for category in db.scalars(select(ShoppingCategory))}
    units = {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    items = []
    for item in shopping_list.items:
        ingredient = ingredients[item.ingredient_id]
        category = categories.get(item.shopping_category_id)
        unit = units[item.unit_id]
        actual_unit = units.get(item.actual_unit_id) if item.actual_unit_id else None
        final_quantity = max(Decimal(item.generated_quantity) + Decimal(item.adjustment_quantity), Decimal("0"))
        items.append(
            {
                "id": item.id,
                "ingredient_id": item.ingredient_id,
                "ingredient_name": ingredient.name,
                "shopping_category_id": item.shopping_category_id,
                "shopping_category_name": category.name if category else "Uncategorized",
                "shopping_category_sort_order": category.sort_order if category else 9999,
                "unit_id": item.unit_id,
                "unit_code": unit.code,
                "unit_family": item.unit_family,
                "required_quantity": item.required_quantity,
                "inventory_quantity": item.inventory_quantity,
                "generated_quantity": item.generated_quantity,
                "adjustment_quantity": item.adjustment_quantity,
                "final_quantity": final_quantity,
                "source_trace": item.source_trace,
                "warning": item.warning,
                "status": item.status,
                "actual_quantity": item.actual_quantity,
                "actual_unit_id": item.actual_unit_id,
                "actual_unit_code": actual_unit.code if actual_unit else None,
                "purchase_date": item.purchase_date,
                "storage_location_id": item.storage_location_id,
                "expiration_date": item.expiration_date,
                "purchase_notes": item.purchase_notes,
                "inventory_lot_id": item.inventory_lot_id,
                "completed_at": item.completed_at,
            }
        )
    items.sort(key=lambda value: (value["shopping_category_sort_order"], value["shopping_category_name"], value["ingredient_name"], value["unit_family"]))
    return {
        "id": shopping_list.id,
        "meal_cycle_id": shopping_list.meal_cycle_id,
        "meal_cycle_name": cycle.name,
        "generated_at": shopping_list.generated_at,
        "items": items,
    }


def _regenerate(db: Session, cycle: MealCycle) -> ShoppingList:
    units = {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    ingredients = {
        ingredient.id: ingredient
        for ingredient in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    inventory_rows = list(
        db.execute(
            select(InventoryLot.ingredient_id, InventoryLot.quantity, InventoryLot.unit_id).where(
                InventoryLot.household_id == HOUSEHOLD_ID,
                InventoryLot.quantity > 0,
            )
        ).all()
    )

    existing = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.meal_cycle_id == cycle.id, ShoppingList.household_id == HOUSEHOLD_ID)
        .options(selectinload(ShoppingList.items))
    )
    if existing is None:
        shopping_list = ShoppingList(household_id=HOUSEHOLD_ID, meal_cycle_id=cycle.id, generated_at=datetime.utcnow())
        db.add(shopping_list)
        db.flush()
        existing_by_key: dict[tuple[int, str], ShoppingListItem] = {}
    else:
        shopping_list = existing
        shopping_list.generated_at = datetime.utcnow()
        existing_by_key = {(item.ingredient_id, item.unit_family): item for item in existing.items}

    requirements: dict[tuple[int, str], list[dict]] = defaultdict(list)
    families_by_ingredient: dict[int, set[str]] = defaultdict(set)
    manual_review_groups: set[tuple[int, str]] = set()

    for slot in sorted(cycle.slots, key=lambda value: (value.day_number, value.sort_order, value.id)):
        planned = slot.planned_meal
        if planned is None:
            continue
        for component in json.loads(planned.scaled_components or "[]"):
            for ingredient_row in component.get("ingredients", []):
                ingredient_id = int(ingredient_row["ingredient_id"])
                unit_id = int(ingredient_row["unit_id"])
                unit = units.get(unit_id)
                if unit is None:
                    raise HTTPException(status_code=409, detail=f"Measurement unit {unit_id} no longer exists")
                key = (ingredient_id, unit.unit_family)
                families_by_ingredient[ingredient_id].add(unit.unit_family)
                requirements[key].append(
                    {
                        "quantity": Decimal(str(ingredient_row["quantity"])),
                        "unit_id": unit_id,
                        "planned_meal_id": planned.id,
                        "cycle_slot_id": slot.id,
                        "day_number": slot.day_number,
                        "meal_name": planned.snapshot_name,
                        "recipe_id": int(component["recipe_id"]),
                    }
                )
                if ingredient_row.get("manual_review"):
                    manual_review_groups.add(key)

    seen_keys: set[tuple[int, str]] = set()
    for key in sorted(requirements):
        seen_keys.add(key)
        ingredient_id, family = key
        ingredient = ingredients.get(ingredient_id)
        if ingredient is None:
            raise HTTPException(status_code=409, detail=f"Ingredient {ingredient_id} no longer exists")
        rows = requirements[key]
        preferred = units.get(ingredient.preferred_unit_id) if ingredient.preferred_unit_id else None
        target_unit = preferred if preferred and preferred.unit_family == family else units[min(row["unit_id"] for row in rows)]

        required = Decimal("0")
        source_trace = []
        for row in rows:
            source_unit = units[row["unit_id"]]
            required += convert_quantity(row["quantity"], source_unit, target_unit)
            source_trace.append(
                {
                    "planned_meal_id": row["planned_meal_id"],
                    "cycle_slot_id": row["cycle_slot_id"],
                    "day_number": row["day_number"],
                    "meal_name": row["meal_name"],
                    "recipe_id": row["recipe_id"],
                    "quantity": str(row["quantity"]),
                    "unit_id": row["unit_id"],
                }
            )

        inventory = Decimal("0")
        for lot_ingredient_id, lot_quantity, lot_unit_id in inventory_rows:
            if lot_ingredient_id != ingredient_id:
                continue
            lot_unit = units.get(lot_unit_id)
            if lot_unit is None or lot_unit.unit_family != family:
                continue
            inventory += convert_quantity(Decimal(lot_quantity), lot_unit, target_unit)

        shortage = max(required - inventory, Decimal("0"))
        warnings = []
        if len(families_by_ingredient[ingredient_id]) > 1:
            warnings.append("Ingredient requirements use incompatible unit families and are kept separate.")
        if key in manual_review_groups:
            warnings.append("One or more recipe ingredients use MANUAL scaling; review this quantity.")

        item = existing_by_key.get(key)
        if item is None:
            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                ingredient_id=ingredient_id,
                unit_family=family,
                adjustment_quantity=Decimal("0"),
                status="PENDING",
            )
            db.add(item)
        item.shopping_category_id = ingredient.shopping_category_id
        item.unit_id = target_unit.id
        item.required_quantity = required
        item.inventory_quantity = inventory
        item.generated_quantity = shortage
        item.source_trace = json.dumps(source_trace, sort_keys=True)
        item.warning = " ".join(warnings) or None

    for key, item in existing_by_key.items():
        if key not in seen_keys and item.status == "PENDING":
            db.delete(item)

    shopping_list_id = shopping_list.id
    db.commit()
    db.expire_all()
    return db.scalar(
        select(ShoppingList)
        .where(ShoppingList.id == shopping_list_id)
        .options(selectinload(ShoppingList.items))
        .execution_options(populate_existing=True)
    )


@router.get("/{cycle_id}", response_model=ShoppingListRead)
def get_shopping_list(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    return _serialize(db, _shopping_list_or_404(db, cycle_id), cycle)


@router.post("/{cycle_id}/regenerate", response_model=ShoppingListRead)
def regenerate_shopping_list(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    return _serialize(db, _regenerate(db, cycle), cycle)


@router.put("/{cycle_id}/items/{item_id}", response_model=ShoppingListRead)
def adjust_shopping_item(cycle_id: int, item_id: int, payload: ShoppingItemAdjustment, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    shopping_list = _shopping_list_or_404(db, cycle_id)
    item = _item_or_404(shopping_list, item_id)
    if item.status != "PENDING":
        raise HTTPException(status_code=409, detail="Completed or skipped shopping items cannot be adjusted")
    item.adjustment_quantity = payload.adjustment_quantity
    db.commit()
    return _serialize(db, shopping_list, cycle)


@router.post("/{cycle_id}/items/{item_id}/complete", response_model=ShoppingListRead)
def complete_shopping_item(cycle_id: int, item_id: int, payload: ShoppingItemComplete, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    shopping_list = _shopping_list_or_404(db, cycle_id)
    item = _item_or_404(shopping_list, item_id)
    if item.status in TERMINAL_STATUSES or item.inventory_lot_id is not None:
        raise HTTPException(status_code=409, detail="Shopping item has already been completed or skipped")

    unit = db.get(MeasurementUnit, payload.actual_unit_id)
    if unit is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    if unit.unit_family != item.unit_family:
        raise HTTPException(status_code=409, detail="Purchased unit must use the same measurement family as the shopping item")
    location = db.get(InventoryLocation, payload.storage_location_id)
    if location is None or location.household_id != HOUSEHOLD_ID or not location.active:
        raise HTTPException(status_code=400, detail="Inventory location not found")

    lot = InventoryLot(
        household_id=HOUSEHOLD_ID,
        ingredient_id=item.ingredient_id,
        location_id=payload.storage_location_id,
        quantity=payload.actual_quantity,
        unit_id=payload.actual_unit_id,
        purchase_date=payload.purchase_date,
        expiration_date=payload.expiration_date,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(lot)
    db.flush()
    db.add(
        InventoryTransaction(
            household_id=HOUSEHOLD_ID,
            lot_id=lot.id,
            transaction_type="PURCHASE",
            quantity_delta=payload.actual_quantity,
            unit_id=payload.actual_unit_id,
            to_location_id=payload.storage_location_id,
            note=payload.notes.strip() if payload.notes else None,
        )
    )
    item.status = "COMPLETED"
    item.actual_quantity = payload.actual_quantity
    item.actual_unit_id = payload.actual_unit_id
    item.purchase_date = payload.purchase_date
    item.storage_location_id = payload.storage_location_id
    item.expiration_date = payload.expiration_date
    item.purchase_notes = payload.notes.strip() if payload.notes else None
    item.inventory_lot_id = lot.id
    item.completed_at = datetime.utcnow()
    db.commit()
    db.expire_all()
    shopping_list = _shopping_list_or_404(db, cycle_id)
    return _serialize(db, shopping_list, cycle)


@router.post("/{cycle_id}/items/{item_id}/skip", response_model=ShoppingListRead)
def skip_shopping_item(cycle_id: int, item_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    shopping_list = _shopping_list_or_404(db, cycle_id)
    item = _item_or_404(shopping_list, item_id)
    if item.status in TERMINAL_STATUSES or item.inventory_lot_id is not None:
        raise HTTPException(status_code=409, detail="Shopping item has already been completed or skipped")
    item.status = "SKIPPED"
    item.completed_at = datetime.utcnow()
    db.commit()
    return _serialize(db, shopping_list, cycle)
