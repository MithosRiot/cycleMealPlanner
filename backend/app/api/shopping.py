import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.reference import MeasurementUnit, ShoppingCategory
from app.models.shopping import ShoppingList, ShoppingListItem
from app.schemas.shopping import ShoppingItemAdjustment, ShoppingListRead
from app.services.units import convert_quantity

router = APIRouter(prefix="/api/shopping", tags=["shopping"])
HOUSEHOLD_ID = 1


def _cycle_or_404(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


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
    inventory_lots = list(
        db.scalars(select(InventoryLot).where(InventoryLot.household_id == HOUSEHOLD_ID, InventoryLot.quantity > 0))
    )

    existing = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.meal_cycle_id == cycle.id, ShoppingList.household_id == HOUSEHOLD_ID)
        .options(selectinload(ShoppingList.items))
    )
    adjustments = {}
    if existing is not None:
        adjustments = {
            (item.ingredient_id, item.unit_family): Decimal(item.adjustment_quantity)
            for item in existing.items
        }
        for item in list(existing.items):
            db.delete(item)
        db.flush()
        shopping_list = existing
        shopping_list.generated_at = datetime.utcnow()
    else:
        shopping_list = ShoppingList(household_id=HOUSEHOLD_ID, meal_cycle_id=cycle.id, generated_at=datetime.utcnow())
        db.add(shopping_list)
        db.flush()

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

    for key in sorted(requirements):
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
            converted = convert_quantity(row["quantity"], source_unit, target_unit)
            required += converted
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
        for lot in inventory_lots:
            if lot.ingredient_id != ingredient_id:
                continue
            lot_unit = units.get(lot.unit_id)
            if lot_unit is None or lot_unit.unit_family != family:
                continue
            inventory += convert_quantity(Decimal(lot.quantity), lot_unit, target_unit)

        shortage = max(required - inventory, Decimal("0"))
        warnings = []
        if len(families_by_ingredient[ingredient_id]) > 1:
            warnings.append("Ingredient requirements use incompatible unit families and are kept separate.")
        if key in manual_review_groups:
            warnings.append("One or more recipe ingredients use MANUAL scaling; review this quantity.")

        db.add(
            ShoppingListItem(
                shopping_list_id=shopping_list.id,
                ingredient_id=ingredient_id,
                shopping_category_id=ingredient.shopping_category_id,
                unit_id=target_unit.id,
                unit_family=family,
                required_quantity=required,
                inventory_quantity=inventory,
                generated_quantity=shortage,
                adjustment_quantity=adjustments.get(key, Decimal("0")),
                source_trace=json.dumps(source_trace, sort_keys=True),
                warning=" ".join(warnings) or None,
            )
        )

    db.commit()
    return db.scalar(
        select(ShoppingList)
        .where(ShoppingList.id == shopping_list.id)
        .options(selectinload(ShoppingList.items))
    )


@router.get("/{cycle_id}", response_model=ShoppingListRead)
def get_shopping_list(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.meal_cycle_id == cycle_id, ShoppingList.household_id == HOUSEHOLD_ID)
        .options(selectinload(ShoppingList.items))
    )
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list has not been generated")
    return _serialize(db, shopping_list, cycle)


@router.post("/{cycle_id}/regenerate", response_model=ShoppingListRead)
def regenerate_shopping_list(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    shopping_list = _regenerate(db, cycle)
    return _serialize(db, shopping_list, cycle)


@router.put("/{cycle_id}/items/{item_id}", response_model=ShoppingListRead)
def adjust_shopping_item(cycle_id: int, item_id: int, payload: ShoppingItemAdjustment, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.meal_cycle_id == cycle_id, ShoppingList.household_id == HOUSEHOLD_ID)
        .options(selectinload(ShoppingList.items))
    )
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list has not been generated")
    item = next((value for value in shopping_list.items if value.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Shopping list item not found")
    item.adjustment_quantity = payload.adjustment_quantity
    db.commit()
    db.refresh(item)
    return _serialize(db, shopping_list, cycle)
