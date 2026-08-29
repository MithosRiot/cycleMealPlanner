import json
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.meal import Meal
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.schemas.planned_meal import PlannedMealAssign, PlannedMealLock, PlannedMealMove, PlannedMealRead, RandomFillResult


router = APIRouter(prefix="/api/meal-cycles", tags=["meal-placement"])
HOUSEHOLD_ID = 1


def _load_slot(db: Session, cycle_id: int, slot_id: int) -> CycleSlot:
    slot = db.scalar(
        select(CycleSlot)
        .join(MealCycle)
        .where(CycleSlot.id == slot_id, CycleSlot.cycle_id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(CycleSlot.slot_definition), selectinload(CycleSlot.planned_meal))
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Cycle slot not found")
    return slot


def _load_meal(db: Session, meal_id: int) -> Meal:
    meal = db.scalar(
        select(Meal)
        .where(Meal.id == meal_id, Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True))
        .options(selectinload(Meal.meal_types), selectinload(Meal.recipes))
    )
    if meal is None:
        raise HTTPException(status_code=400, detail="Active meal not found")
    return meal


def _snapshot(meal: Meal) -> dict[str, str | None]:
    components = [
        {
            "recipe_id": component.recipe_id,
            "serving_multiplier": str(component.serving_multiplier),
            "default_servings": str(component.default_servings) if component.default_servings is not None else None,
            "sort_order": component.sort_order,
            "notes": component.notes,
        }
        for component in meal.recipes
    ]
    return {
        "snapshot_name": meal.name,
        "snapshot_description": meal.description,
        "snapshot_meal_types": json.dumps([item.meal_type for item in meal.meal_types]),
        "snapshot_components": json.dumps(components),
    }


def _place(db: Session, slot: CycleSlot, meal: Meal) -> PlannedMeal:
    if slot.planned_meal is not None:
        if slot.planned_meal.locked:
            raise HTTPException(status_code=409, detail="Placement is locked")
        db.delete(slot.planned_meal)
        db.flush()
    planned = PlannedMeal(cycle_slot_id=slot.id, meal_id=meal.id, locked=False, **_snapshot(meal))
    db.add(planned)
    db.flush()
    return planned


@router.post("/{cycle_id}/slots/{slot_id}/planned-meal", response_model=PlannedMealRead, status_code=status.HTTP_201_CREATED)
def assign_meal(cycle_id: int, slot_id: int, payload: PlannedMealAssign, db: Session = Depends(get_db)) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    meal = _load_meal(db, payload.meal_id)
    planned = _place(db, slot, meal)
    db.commit()
    db.refresh(planned)
    return planned


@router.delete("/{cycle_id}/slots/{slot_id}/planned-meal", status_code=status.HTTP_204_NO_CONTENT)
def remove_meal(cycle_id: int, slot_id: int, db: Session = Depends(get_db)) -> None:
    slot = _load_slot(db, cycle_id, slot_id)
    if slot.planned_meal is None:
        return
    if slot.planned_meal.locked:
        raise HTTPException(status_code=409, detail="Placement is locked")
    db.delete(slot.planned_meal)
    db.commit()


@router.put("/{cycle_id}/slots/{slot_id}/planned-meal/lock", response_model=PlannedMealRead)
def set_lock(cycle_id: int, slot_id: int, payload: PlannedMealLock, db: Session = Depends(get_db)) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    if slot.planned_meal is None:
        raise HTTPException(status_code=404, detail="No planned meal in this slot")
    slot.planned_meal.locked = payload.locked
    db.commit()
    db.refresh(slot.planned_meal)
    return slot.planned_meal


@router.post("/{cycle_id}/slots/{slot_id}/planned-meal/move", response_model=PlannedMealRead)
def move_meal(cycle_id: int, slot_id: int, payload: PlannedMealMove, db: Session = Depends(get_db)) -> PlannedMeal:
    source = _load_slot(db, cycle_id, slot_id)
    target = _load_slot(db, cycle_id, payload.target_cycle_slot_id)
    if source.planned_meal is None:
        raise HTTPException(status_code=404, detail="No planned meal in source slot")
    if source.planned_meal.locked:
        raise HTTPException(status_code=409, detail="Placement is locked")
    if target.planned_meal is not None:
        raise HTTPException(status_code=409, detail="Target slot is occupied")
    planned = source.planned_meal
    planned.cycle_slot_id = target.id
    db.commit()
    db.refresh(planned)
    return planned


@router.post("/{cycle_id}/random-fill", response_model=RandomFillResult)
def random_fill(cycle_id: int, db: Session = Depends(get_db)) -> RandomFillResult:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(
            selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition),
            selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal),
        )
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")

    meals = list(
        db.scalars(
            select(Meal)
            .where(Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True))
            .options(selectinload(Meal.meal_types), selectinload(Meal.recipes))
        ).unique()
    )
    if not meals:
        return RandomFillResult(filled_count=0)

    filled = 0
    for slot in cycle.slots:
        if slot.planned_meal is not None:
            continue
        label = slot.slot_definition.label.strip().casefold()
        eligible = [meal for meal in meals if any(mt.meal_type.casefold() == label for mt in meal.meal_types)]
        if not eligible:
            continue
        _place(db, slot, random.choice(eligible))
        filled += 1

    db.commit()
    return RandomFillResult(filled_count=filled)
