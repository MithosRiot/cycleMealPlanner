from __future__ import annotations

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.planned_meals import _load_slot
from app.database.session import get_db
from app.models.completion import MealCompletion
from app.models.inventory import InventoryLot
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.production import Leftover, MealCompletionOutput
from app.models.recipe_output import RecipeOutput
from app.models.reference import MeasurementUnit
from app.schemas.planned_meal import PlannedMealRead, ProducedSourceAssign, ProducedSourceOption
from app.services.production_coverage import reconcile_production_coverage, release_coverage_for_planned, reserved_for_lot

router = APIRouter(tags=["produced-source-planning"])
HOUSEHOLD_ID = 1
SERVING_UNIT_ID = 16


def _origin_or_404(db: Session, planned_meal_id: int) -> PlannedMeal:
    planned = db.scalar(
        select(PlannedMeal)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .join(MealCycle, MealCycle.id == CycleSlot.cycle_id)
        .where(PlannedMeal.id == planned_meal_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(PlannedMeal.cycle_slot).selectinload(CycleSlot.cycle))
    )
    if planned is None:
        raise HTTPException(status_code=404, detail="Source Planned Meal not found")
    if planned.source_type != "SAVED_MEAL":
        raise HTTPException(status_code=422, detail="Produced stock must originate from a saved Meal placement")
    return planned


def _lot_availability(db: Session, lot: InventoryLot | None) -> tuple[Decimal, Decimal, Decimal]:
    if lot is None:
        return Decimal("0"), Decimal("0"), Decimal("0")
    physical = Decimal(lot.quantity)
    reserved = reserved_for_lot(db, lot.id)
    return physical, reserved, max(physical - reserved, Decimal("0"))


def _leftover_option(db: Session, origin: PlannedMeal, unit: MeasurementUnit) -> ProducedSourceOption | None:
    planned_quantity = Decimal(origin.planned_leftover_servings)
    if planned_quantity <= 0:
        return None
    leftover = db.scalar(select(Leftover).where(Leftover.planned_meal_id == origin.id).order_by(Leftover.id))
    lot = db.get(InventoryLot, leftover.inventory_lot_id) if leftover and leftover.inventory_lot_id else None
    physical, reserved, available = _lot_availability(db, lot)
    return ProducedSourceOption(
        source_type="LEFTOVER",
        source_origin_planned_meal_id=origin.id,
        source_record_id=leftover.id if leftover else None,
        source_recipe_output_id=None,
        source_name=f"Leftover: {origin.snapshot_name}",
        source_meal_id=origin.meal_id,
        unit_id=SERVING_UNIT_ID,
        unit_code=unit.code,
        planned_quantity=planned_quantity,
        physical_quantity=physical,
        reserved_quantity=reserved,
        available_quantity=available,
        lot_id=lot.id if lot else None,
        expiration_date=lot.expiration_date if lot else None,
    )


def _produced_output_options(db: Session, origin: PlannedMeal, units: dict[int, MeasurementUnit]) -> list[ProducedSourceOption]:
    completion = db.scalar(select(MealCompletion).where(MealCompletion.planned_meal_id == origin.id))
    if completion is None:
        return []
    outputs = list(db.scalars(
        select(MealCompletionOutput)
        .where(MealCompletionOutput.completion_id == completion.id)
        .order_by(MealCompletionOutput.id)
    ))
    result: list[ProducedSourceOption] = []
    for output in outputs:
        unit = units.get(output.unit_id)
        if unit is None:
            continue
        lot = db.get(InventoryLot, output.inventory_lot_id) if output.inventory_lot_id else None
        physical, reserved, available = _lot_availability(db, lot)
        result.append(ProducedSourceOption(
            source_type="RECIPE_OUTPUT",
            source_origin_planned_meal_id=origin.id,
            source_record_id=output.id,
            source_recipe_output_id=output.recipe_output_id,
            source_name=f"Recipe output: {output.output_name}",
            source_meal_id=origin.meal_id,
            unit_id=output.unit_id,
            unit_code=unit.code,
            planned_quantity=Decimal(output.calculated_quantity),
            physical_quantity=physical,
            reserved_quantity=reserved,
            available_quantity=available,
            lot_id=lot.id if lot else None,
            expiration_date=lot.expiration_date if lot else None,
        ))
    return result


@router.get("/api/produced-source-options", response_model=list[ProducedSourceOption])
def produced_source_options(db: Session = Depends(get_db)) -> list[ProducedSourceOption]:
    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    serving_unit = units.get(SERVING_UNIT_ID)
    if serving_unit is None:
        return []
    origins = list(db.scalars(
        select(PlannedMeal)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .join(MealCycle, MealCycle.id == CycleSlot.cycle_id)
        .where(MealCycle.household_id == HOUSEHOLD_ID, PlannedMeal.source_type == "SAVED_MEAL")
        .order_by(MealCycle.id, CycleSlot.day_number, CycleSlot.sort_order, PlannedMeal.id)
    ))
    result: list[ProducedSourceOption] = []
    for origin in origins:
        leftover = _leftover_option(db, origin, serving_unit)
        if leftover is not None:
            result.append(leftover)
        result.extend(_produced_output_options(db, origin, units))
    return result


def _validate_source(db: Session, payload: ProducedSourceAssign, origin: PlannedMeal) -> tuple[str, int | None, int | None]:
    unit = db.get(MeasurementUnit, payload.unit_id)
    if unit is None:
        raise HTTPException(status_code=422, detail="Unknown source measurement unit")

    if payload.source_type == "LEFTOVER":
        if payload.unit_id != SERVING_UNIT_ID:
            raise HTTPException(status_code=422, detail="Leftover Meal coverage must use servings")
        if Decimal(origin.planned_leftover_servings) <= 0:
            raise HTTPException(status_code=422, detail="Source Meal does not plan any leftover servings")
        leftover = db.get(Leftover, payload.source_record_id) if payload.source_record_id is not None else None
        if leftover is not None and leftover.planned_meal_id != origin.id:
            raise HTTPException(status_code=422, detail="Leftover record does not belong to the selected source Meal")
        return f"Leftover: {origin.snapshot_name}", leftover.id if leftover else None, None

    output_record = db.get(MealCompletionOutput, payload.source_record_id) if payload.source_record_id is not None else None
    if output_record is not None:
        completion = db.get(MealCompletion, output_record.completion_id)
        if completion is None or completion.planned_meal_id != origin.id:
            raise HTTPException(status_code=422, detail="Recipe output record does not belong to the selected source Meal")
        if output_record.unit_id != payload.unit_id:
            raise HTTPException(status_code=422, detail="Recipe output unit does not match the selected produced output")
        return f"Recipe output: {output_record.output_name}", output_record.id, output_record.recipe_output_id

    recipe_output = db.get(RecipeOutput, payload.source_recipe_output_id) if payload.source_recipe_output_id is not None else None
    if recipe_output is None or recipe_output.unit_id != payload.unit_id:
        raise HTTPException(status_code=422, detail="Recipe output source is not valid")
    recipe_ids = {int(row.get("recipe_id")) for row in json.loads(origin.scaled_components or "[]") if row.get("recipe_id") is not None}
    if recipe_output.recipe_id not in recipe_ids:
        raise HTTPException(status_code=422, detail="Recipe output is not produced by the selected source Meal")
    return f"Recipe output: {recipe_output.name}", None, recipe_output.id


@router.post("/api/meal-cycles/{cycle_id}/slots/{slot_id}/planned-source", response_model=PlannedMealRead, status_code=status.HTTP_201_CREATED)
def assign_produced_source(cycle_id: int, slot_id: int, payload: ProducedSourceAssign, db: Session = Depends(get_db)) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    origin = _origin_or_404(db, payload.source_origin_planned_meal_id)
    if origin.cycle_slot_id == slot.id:
        raise HTTPException(status_code=422, detail="A Meal cannot consume produced stock from itself")
    source_name, source_record_id, source_recipe_output_id = _validate_source(db, payload, origin)

    if slot.planned_meal is not None:
        if slot.planned_meal.locked:
            raise HTTPException(status_code=409, detail="Placement is locked")
        release_coverage_for_planned(db, slot.planned_meal.id, "REPLACED")
        db.delete(slot.planned_meal)
        db.flush()

    planned = PlannedMeal(
        cycle_slot_id=slot.id,
        meal_id=origin.meal_id,
        source_type=payload.source_type,
        source_origin_planned_meal_id=origin.id,
        source_record_id=source_record_id,
        source_recipe_output_id=source_recipe_output_id,
        source_quantity=payload.quantity,
        source_unit_id=payload.unit_id,
        locked=False,
        planned_servings=max(payload.quantity, Decimal("0.001")),
        planned_leftover_servings=Decimal("0"),
        component_serving_overrides="{}",
        scaled_components="[]",
        snapshot_name=source_name,
        snapshot_description=f"Planned use of {source_name} from {origin.snapshot_name}",
        snapshot_meal_types=origin.snapshot_meal_types,
        snapshot_components="[]",
    )
    db.add(planned)
    db.flush()
    reconcile_production_coverage(db)
    db.commit()
    db.refresh(planned)
    return planned
