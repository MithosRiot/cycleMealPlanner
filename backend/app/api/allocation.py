from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.reference import MeasurementUnit
from app.schemas.allocation import AllocationPreviewRead, AllocationPreviewRequest, CycleAllocationPreviewRead
from app.services.inventory_allocation import allocate_requirement, allocate_requirement_sequence

router = APIRouter(tags=["allocation"])
HOUSEHOLD_ID = 1


def _cycle_or_404(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(
            selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal),
            selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition),
        )
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


@router.post("/api/inventory-allocation/preview", response_model=AllocationPreviewRead)
def preview_inventory_allocation(payload: AllocationPreviewRequest, db: Session = Depends(get_db)) -> dict:
    ingredient = db.scalar(
        select(Ingredient).where(Ingredient.id == payload.ingredient_id, Ingredient.household_id == HOUSEHOLD_ID)
    )
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    unit = db.get(MeasurementUnit, payload.unit_id)
    if unit is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    if payload.exclude_cycle_id is not None:
        _cycle_or_404(db, payload.exclude_cycle_id)

    result = allocate_requirement(
        db,
        ingredient=ingredient,
        quantity=payload.quantity,
        target_unit=unit,
        use_date=payload.use_date,
        exclude_cycle_id=payload.exclude_cycle_id,
    )
    return {**result, "ingredient_name": ingredient.name}


@router.get("/api/meal-cycles/{cycle_id}/allocation-preview", response_model=CycleAllocationPreviewRead)
def preview_cycle_allocation(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    ingredients = {
        row.id: row.name
        for row in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    requirements: list[dict] = []
    for slot in sorted(cycle.slots, key=lambda row: (row.day_number, row.sort_order, row.id)):
        planned = slot.planned_meal
        if planned is None:
            continue
        use_date = cycle.start_date + timedelta(days=slot.day_number - 1) if cycle.start_date is not None else None
        try:
            components = json.loads(planned.scaled_components or "[]")
        except json.JSONDecodeError:
            components = []
        for component in components:
            for row in component.get("ingredients", []):
                quantity = Decimal(str(row.get("quantity", "0")))
                if quantity <= 0:
                    continue
                requirements.append(
                    {
                        "ingredient_id": int(row["ingredient_id"]),
                        "quantity": quantity,
                        "unit_id": int(row["unit_id"]),
                        "use_date": use_date,
                        "planned_meal_id": planned.id,
                        "meal_name": planned.snapshot_name,
                        "day_number": slot.day_number,
                        "slot_label": slot.slot_definition.label,
                        "recipe_id": int(component["recipe_id"]),
                    }
                )

    requirements.sort(
        key=lambda row: (
            row["use_date"] is None,
            row["use_date"] or cycle.start_date,
            row["day_number"],
            row["planned_meal_id"],
            row["recipe_id"],
            row["ingredient_id"],
        )
    )
    allocated = allocate_requirement_sequence(db, requirements, exclude_cycle_id=cycle.id)
    for row in allocated:
        row["ingredient_name"] = ingredients.get(row["ingredient_id"])
    return {
        "meal_cycle_id": cycle.id,
        "meal_cycle_name": cycle.name,
        "requirements": allocated,
    }
