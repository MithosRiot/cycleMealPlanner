from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.shopping import _regenerate
from app.models.completion import MealCompletion
from app.models.gather import GatherLotSelection
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.planned_meal_revision import PlannedMealRevision
from app.models.reservation import InventoryReservation
from app.models.shopping import ShoppingList
from app.services.production_coverage import reconcile_production_coverage

HOUSEHOLD_ID = 1
INGREDIENT_REQUIREMENT_SOURCES = {"SAVED_MEAL", "DIRECT_RECIPE"}


def assert_occurrence_editable(db: Session, planned: PlannedMeal | None) -> None:
    if planned is None:
        return
    completion = db.scalar(select(MealCompletion).where(MealCompletion.planned_meal_id == planned.id))
    if completion is not None and completion.status == "FINALIZED":
        raise HTTPException(status_code=409, detail=f"{planned.snapshot_name} is finalized and cannot be revised")


def record_revision(db: Session, cycle_id: int, planned: PlannedMeal | None, action: str) -> None:
    if planned is None:
        return
    cycle = db.get(MealCycle, cycle_id)
    if cycle is None or cycle.status != "ACTIVE":
        return
    db.add(PlannedMealRevision(
        cycle_id=cycle_id,
        cycle_slot_id=planned.cycle_slot_id,
        planned_meal_id=planned.id,
        action=action,
        source_type=planned.source_type,
        snapshot_name=planned.snapshot_name,
        snapshot_description=planned.snapshot_description,
        planned_servings=planned.planned_servings,
        planned_leftover_servings=planned.planned_leftover_servings,
        component_serving_overrides=planned.component_serving_overrides,
        scaled_components=planned.scaled_components,
        changed_at=datetime.utcnow(),
    ))


def _completed_ids(db: Session) -> set[int]:
    return set(db.scalars(select(MealCompletion.planned_meal_id).where(MealCompletion.status == "FINALIZED")))


def _requirements(db: Session, cycle_id: int) -> list[dict]:
    completed = _completed_ids(db)
    rows = db.execute(
        select(PlannedMeal.id, PlannedMeal.scaled_components, PlannedMeal.source_type)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .where(CycleSlot.cycle_id == cycle_id)
    ).all()
    result: list[dict] = []
    for planned_id, raw, source_type in rows:
        if int(planned_id) in completed or source_type not in INGREDIENT_REQUIREMENT_SOURCES:
            continue
        try:
            components = json.loads(raw or "[]")
        except json.JSONDecodeError:
            components = []
        for component in components:
            for ingredient in component.get("ingredients", []):
                quantity = Decimal(str(ingredient.get("quantity", "0")))
                if quantity <= 0:
                    continue
                result.append({
                    "planned_meal_id": int(planned_id),
                    "meal_recipe_id": int(component.get("meal_recipe_id")) if component.get("meal_recipe_id") is not None else None,
                    "recipe_id": int(component["recipe_id"]),
                    "recipe_ingredient_id": int(ingredient["recipe_ingredient_id"]) if ingredient.get("recipe_ingredient_id") is not None else None,
                    "ingredient_id": int(ingredient["ingredient_id"]),
                    "quantity": quantity,
                    "unit_id": int(ingredient["unit_id"]),
                })
    return result


def _reservation_key(row: dict | InventoryReservation) -> tuple[int, int | None, int | None]:
    if isinstance(row, InventoryReservation):
        return row.planned_meal_id, row.meal_recipe_id, row.recipe_ingredient_id
    return row["planned_meal_id"], row["meal_recipe_id"], row["recipe_ingredient_id"]


def reconcile_inventory_reservations(db: Session, cycle_id: int) -> None:
    requirements = _requirements(db, cycle_id)
    completed = _completed_ids(db)
    existing = list(db.scalars(select(InventoryReservation).where(InventoryReservation.cycle_id == cycle_id)))
    by_key = {_reservation_key(row): row for row in existing}
    seen: set[tuple[int, int | None, int | None]] = set()

    for requirement in requirements:
        key = _reservation_key(requirement)
        seen.add(key)
        model = by_key.get(key)
        if model is None:
            db.add(InventoryReservation(
                household_id=HOUSEHOLD_ID,
                cycle_id=cycle_id,
                planned_meal_id=requirement["planned_meal_id"],
                meal_recipe_id=requirement["meal_recipe_id"],
                recipe_id=requirement["recipe_id"],
                recipe_ingredient_id=requirement["recipe_ingredient_id"],
                ingredient_id=requirement["ingredient_id"],
                quantity=requirement["quantity"],
                unit_id=requirement["unit_id"],
                status="ACTIVE",
            ))
        else:
            model.recipe_id = requirement["recipe_id"]
            model.ingredient_id = requirement["ingredient_id"]
            model.quantity = requirement["quantity"]
            model.unit_id = requirement["unit_id"]
            if model.planned_meal_id not in completed:
                model.status = "ACTIVE"

    for model in existing:
        if (model.planned_meal_id in completed or _reservation_key(model) not in seen) and model.status == "ACTIVE":
            model.status = "RELEASED"


def reconcile_active_cycle(
    db: Session,
    cycle_id: int,
    *,
    invalidate_gather_for: set[int] | None = None,
) -> None:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    if cycle.status != "ACTIVE":
        return

    if invalidate_gather_for:
        db.execute(delete(GatherLotSelection).where(GatherLotSelection.planned_meal_id.in_(invalidate_gather_for)))

    reconcile_inventory_reservations(db, cycle_id)
    reconcile_production_coverage(db)

    shopping_list = db.scalar(select(ShoppingList).where(ShoppingList.meal_cycle_id == cycle_id))
    if shopping_list is not None:
        db.flush()
        db.expire(cycle, ["slots"])
        cycle = db.scalar(
            select(MealCycle)
            .where(MealCycle.id == cycle_id)
            .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
        )
        _regenerate(db, cycle, commit=False)

    db.flush()
