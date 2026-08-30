from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.reference import MeasurementUnit
from app.services.units import convert_quantity

router = APIRouter(prefix="/api/meal-cycles", tags=["expiration-planning"])
HOUSEHOLD_ID = 1


def _load_cycle(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _planned_requirements(planned: PlannedMeal) -> dict[int, list[tuple[Decimal, int]]]:
    result: dict[int, list[tuple[Decimal, int]]] = defaultdict(list)
    for component in json.loads(planned.scaled_components or "[]"):
        for row in component.get("ingredients", []):
            result[int(row["ingredient_id"])].append((Decimal(str(row["quantity"])), int(row["unit_id"])))
    return result


@router.get("/{cycle_id}/expiration-suggestions")
def expiration_suggestions(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _load_cycle(db, cycle_id)
    if cycle.start_date is None:
        raise HTTPException(status_code=409, detail="Set a cycle start date to evaluate expiration timing")

    units = {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    ingredients = {
        ingredient.id: ingredient
        for ingredient in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    lots_by_ingredient: dict[int, list[InventoryLot]] = defaultdict(list)
    for lot in db.scalars(
        select(InventoryLot).where(
            InventoryLot.household_id == HOUSEHOLD_ID,
            InventoryLot.quantity > 0,
            InventoryLot.expiration_date.is_not(None),
        )
    ):
        lots_by_ingredient[lot.ingredient_id].append(lot)

    suggestions: list[dict] = []
    for slot in sorted(cycle.slots, key=lambda value: (value.day_number, value.sort_order, value.id)):
        planned = slot.planned_meal
        if planned is None:
            continue
        planned_date = cycle.start_date + timedelta(days=slot.day_number - 1)
        requirements = _planned_requirements(planned)
        expiring_matches: list[dict] = []
        urgency_days: int | None = None

        for ingredient_id, rows in requirements.items():
            ingredient = ingredients.get(ingredient_id)
            if ingredient is None:
                continue
            for lot in sorted(lots_by_ingredient.get(ingredient_id, []), key=lambda value: (value.expiration_date or date.max, value.id)):
                if lot.expiration_date is None:
                    continue
                days_until_expiration = (lot.expiration_date - planned_date).days
                if days_until_expiration < 0:
                    continue

                lot_unit = units.get(lot.unit_id)
                if lot_unit is None:
                    continue
                needed_in_lot_unit = Decimal("0")
                convertible = False
                for quantity, unit_id in rows:
                    source_unit = units.get(unit_id)
                    if source_unit is None or source_unit.unit_family != lot_unit.unit_family:
                        continue
                    needed_in_lot_unit += convert_quantity(quantity, source_unit, lot_unit)
                    convertible = True
                if not convertible or needed_in_lot_unit <= 0:
                    continue

                usable = min(Decimal(lot.quantity), needed_in_lot_unit)
                if usable <= 0:
                    continue
                urgency_days = days_until_expiration if urgency_days is None else min(urgency_days, days_until_expiration)
                expiring_matches.append(
                    {
                        "ingredient_id": ingredient_id,
                        "ingredient_name": ingredient.name,
                        "inventory_lot_id": lot.id,
                        "expiration_date": lot.expiration_date,
                        "days_until_expiration_on_planned_date": days_until_expiration,
                        "usable_quantity": usable,
                        "unit_id": lot.unit_id,
                        "unit_code": lot_unit.code,
                    }
                )

        if not expiring_matches:
            continue

        earlier_empty_days = sorted(
            {
                candidate.day_number
                for candidate in cycle.slots
                if candidate.day_number < slot.day_number
                and candidate.sort_order == slot.sort_order
                and candidate.planned_meal is None
            }
        )
        earlier_swap_days = sorted(
            {
                candidate.day_number
                for candidate in cycle.slots
                if candidate.day_number < slot.day_number
                and candidate.sort_order == slot.sort_order
                and candidate.planned_meal is not None
                and not candidate.planned_meal.locked
            }
        )

        suggestions.append(
            {
                "planned_meal_id": planned.id,
                "cycle_slot_id": slot.id,
                "meal_id": planned.meal_id,
                "meal_name": planned.snapshot_name,
                "day_number": slot.day_number,
                "planned_date": planned_date,
                "urgency_days": urgency_days,
                "expiring_matches": expiring_matches,
                "suggested_empty_day_numbers": earlier_empty_days,
                "suggested_swap_day_numbers": earlier_swap_days,
                "can_move_earlier": bool(earlier_empty_days),
                "can_swap_earlier": bool(earlier_swap_days),
            }
        )

    suggestions.sort(key=lambda row: (row["urgency_days"] if row["urgency_days"] is not None else 999999, row["day_number"], row["meal_name"]))
    return {
        "meal_cycle_id": cycle.id,
        "meal_cycle_name": cycle.name,
        "start_date": cycle.start_date,
        "suggestions": suggestions,
    }
