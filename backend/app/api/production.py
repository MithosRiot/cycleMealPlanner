from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.completion import _load_completion, _payload, _planned_or_404
from app.database.session import get_db
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.production import Leftover, MealCompletionOutput
from app.models.recipe import Recipe
from app.models.recipe_output import RecipeOutput
from app.models.reference import InventoryLocation, MeasurementUnit
from app.schemas.completion import (
    CompletionProductionCommitInput,
    CompletionProductionPreview,
    CompletionProductionRead,
)

router = APIRouter(prefix="/api/planned-meals", tags=["meal-completion-production"])
HOUSEHOLD_ID = 1
SERVING_UNIT_ID = 16


def _production_rows(db: Session, completion, actual_servings_produced: Decimal) -> list[dict]:
    components = json.loads(completion.snapshot_scaled_components or "[]")
    planned_total = Decimal(completion.snapshot_planned_servings) + Decimal(completion.snapshot_planned_leftover_servings)
    meal_scale = Decimal("0") if planned_total == 0 else actual_servings_produced / planned_total
    recipe_ids = {int(component["recipe_id"]) for component in components}
    recipes = {row.id: row for row in db.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids)))} if recipe_ids else {}
    outputs = list(db.scalars(
        select(RecipeOutput)
        .where(RecipeOutput.recipe_id.in_(recipe_ids), RecipeOutput.active.is_(True))
        .order_by(RecipeOutput.recipe_id, RecipeOutput.sort_order, RecipeOutput.id)
    )) if recipe_ids else []
    by_recipe: dict[int, list[RecipeOutput]] = {}
    for output in outputs:
        by_recipe.setdefault(output.recipe_id, []).append(output)
    unit_ids = {output.unit_id for output in outputs}
    units = {row.id: row for row in db.scalars(select(MeasurementUnit).where(MeasurementUnit.id.in_(unit_ids)))} if unit_ids else {}

    result: list[dict] = []
    for index, component in enumerate(components):
        recipe_id = int(component["recipe_id"])
        recipe = recipes.get(recipe_id)
        if recipe is None:
            continue
        component_key = int(component.get("meal_recipe_id") or -(index + 1))
        planned_component_servings = Decimal(str(
            component.get("requested_servings")
            or component.get("servings")
            or planned_total
        ))
        actual_component_servings = planned_component_servings * meal_scale
        for output in by_recipe.get(recipe_id, []):
            unit = units.get(output.unit_id)
            if unit is None:
                raise HTTPException(status_code=409, detail=f"Stored unit for Recipe output {output.name} no longer exists")
            calculated = Decimal(output.quantity) * actual_component_servings / Decimal(recipe.base_servings)
            result.append({
                "component_key": component_key,
                "recipe_id": recipe.id,
                "recipe_name": component.get("recipe_name") or recipe.name,
                "recipe_output_id": output.id,
                "output_name": output.name,
                "recipe_base_servings": Decimal(recipe.base_servings),
                "planned_component_servings": planned_component_servings,
                "base_quantity": Decimal(output.quantity),
                "calculated_quantity": calculated,
                "unit_id": unit.id,
                "unit_code": unit.code,
            })
    return result


def _validate_location(db: Session, location_id: int | None, label: str) -> None:
    if location_id is None:
        raise HTTPException(status_code=422, detail=f"{label} location is required when quantity is greater than zero")
    location = db.get(InventoryLocation, location_id)
    if location is None or location.household_id != HOUSEHOLD_ID or not location.active:
        raise HTTPException(status_code=422, detail=f"{label} location is not active")


def _completion_payload(db: Session, planned, completion) -> dict:
    body = _payload(db, planned, completion)
    body["actual_servings_produced"] = completion.actual_servings_produced
    body["actual_servings_eaten"] = completion.actual_servings_eaten
    body["production_committed_at"] = completion.production_committed_at
    return body


def _read_production(db: Session, planned, completion) -> dict:
    leftover = db.scalar(select(Leftover).where(Leftover.completion_id == completion.id))
    if leftover is None:
        raise HTTPException(status_code=404, detail="Completion production has not been committed")
    outputs = list(db.scalars(
        select(MealCompletionOutput)
        .where(MealCompletionOutput.completion_id == completion.id)
        .order_by(MealCompletionOutput.component_key, MealCompletionOutput.id)
    ))
    return {"completion": _completion_payload(db, planned, completion), "leftover": leftover, "outputs": outputs}


@router.get("/{planned_meal_id}/completion/production-preview", response_model=CompletionProductionPreview)
def production_preview(planned_meal_id: int, actual_servings_produced: Decimal | None = None, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None or completion.status != "FINALIZED":
        raise HTTPException(status_code=409, detail="Meal completion must be finalized before recording production")
    default_produced = Decimal(completion.snapshot_planned_servings) + Decimal(completion.snapshot_planned_leftover_servings)
    produced = default_produced if actual_servings_produced is None else actual_servings_produced
    if produced < 0:
        raise HTTPException(status_code=422, detail="Actual servings produced cannot be negative")
    default_eaten = min(Decimal(completion.snapshot_planned_servings), produced)
    return {
        "planned_servings": completion.snapshot_planned_servings,
        "planned_leftover_servings": completion.snapshot_planned_leftover_servings,
        "default_actual_servings_produced": produced,
        "default_actual_servings_eaten": default_eaten,
        "default_leftover_servings": produced - default_eaten,
        "outputs": _production_rows(db, completion, produced),
    }


@router.get("/{planned_meal_id}/completion/production", response_model=CompletionProductionRead)
def get_production(planned_meal_id: int, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None:
        raise HTTPException(status_code=404, detail="Meal completion not found")
    return _read_production(db, planned, completion)


@router.post("/{planned_meal_id}/completion/production", response_model=CompletionProductionRead)
def commit_production(planned_meal_id: int, payload: CompletionProductionCommitInput, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None or completion.status != "FINALIZED":
        raise HTTPException(status_code=409, detail="Meal completion must be finalized before recording production")
    if completion.production_committed_at is not None:
        return _read_production(db, planned, completion)
    if payload.actual_servings_eaten > payload.actual_servings_produced:
        raise HTTPException(status_code=422, detail="Actual servings eaten cannot exceed actual servings produced")

    leftover_quantity = payload.actual_servings_produced - payload.actual_servings_eaten
    if leftover_quantity > 0:
        _validate_location(db, payload.leftover_location_id, "Leftover")

    calculated = _production_rows(db, completion, payload.actual_servings_produced)
    expected_keys = {(row["component_key"], row["recipe_output_id"]) for row in calculated}
    supplied_keys = {(row.component_key, row.recipe_output_id) for row in payload.outputs}
    if len(supplied_keys) != len(payload.outputs):
        raise HTTPException(status_code=422, detail="Duplicate Recipe output production row")
    if supplied_keys != expected_keys:
        raise HTTPException(status_code=422, detail="Production commit must include every active Recipe output exactly once")
    supplied = {(row.component_key, row.recipe_output_id): row for row in payload.outputs}
    for row in calculated:
        item = supplied[(row["component_key"], row["recipe_output_id"])]
        if item.actual_quantity > 0:
            _validate_location(db, item.location_id, f"Recipe output {row['output_name']}")

    ingredient_transaction_count = db.scalar(
        select(InventoryTransaction.id)
        .where(InventoryTransaction.transaction_type == "CONSUME", InventoryTransaction.note.like(f"Meal completion #{completion.id} /%"))
        .limit(1)
    )
    if ingredient_transaction_count is None and any(Decimal(row.actual_quantity) > 0 for row in completion.usages):
        raise HTTPException(status_code=409, detail="Finalized ingredient consumption provenance is missing")

    try:
        now = datetime.utcnow()
        leftover = Leftover(
            completion_id=completion.id,
            planned_meal_id=planned.id,
            source_meal_id=planned.meal_id,
            source_recipe_id=planned.source_recipe_id,
            source_meal_name=completion.snapshot_name,
            source_components=completion.snapshot_scaled_components,
            actual_servings_produced=payload.actual_servings_produced,
            actual_servings_eaten=payload.actual_servings_eaten,
            leftover_servings=leftover_quantity,
            serving_unit="serving",
            location_id=payload.leftover_location_id if leftover_quantity > 0 else None,
            expiration_date=payload.leftover_expiration_date if leftover_quantity > 0 else None,
            notes=payload.leftover_notes.strip() if payload.leftover_notes else None,
            status="AVAILABLE" if leftover_quantity > 0 else "NONE",
            created_at=now,
        )
        db.add(leftover)
        db.flush()
        if leftover_quantity > 0:
            lot = InventoryLot(
                household_id=HOUSEHOLD_ID,
                ingredient_id=None,
                source_type="LEFTOVER",
                source_id=leftover.id,
                source_name=f"Leftover: {completion.snapshot_name}",
                location_id=payload.leftover_location_id,
                quantity=leftover_quantity,
                unit_id=SERVING_UNIT_ID,
                purchase_date=None,
                opened_date=None,
                expiration_date=payload.leftover_expiration_date,
                frozen_date=None,
                thawed_date=None,
                notes=payload.leftover_notes.strip() if payload.leftover_notes else None,
            )
            db.add(lot)
            db.flush()
            transaction = InventoryTransaction(
                household_id=HOUSEHOLD_ID,
                lot_id=lot.id,
                transaction_type="PRODUCTION",
                quantity_delta=leftover_quantity,
                unit_id=SERVING_UNIT_ID,
                to_location_id=payload.leftover_location_id,
                note=f"Meal completion {completion.id} produced leftover {leftover.id}",
                created_at=now,
            )
            db.add(transaction)
            db.flush()
            leftover.inventory_lot_id = lot.id
            leftover.inventory_transaction_id = transaction.id

        for row in calculated:
            item = supplied[(row["component_key"], row["recipe_output_id"])]
            output_record = MealCompletionOutput(
                completion_id=completion.id,
                component_key=row["component_key"],
                recipe_id=row["recipe_id"],
                recipe_name=row["recipe_name"],
                recipe_output_id=row["recipe_output_id"],
                output_name=row["output_name"],
                recipe_base_servings=row["recipe_base_servings"],
                planned_component_servings=row["planned_component_servings"],
                base_quantity=row["base_quantity"],
                calculated_quantity=row["calculated_quantity"],
                actual_quantity=item.actual_quantity,
                quantity_overridden=abs(item.actual_quantity - row["calculated_quantity"]) > Decimal("0.000001"),
                unit_id=row["unit_id"],
                unit_code=row["unit_code"],
                location_id=item.location_id if item.actual_quantity > 0 else None,
                expiration_date=item.expiration_date if item.actual_quantity > 0 else None,
                notes=item.notes.strip() if item.notes else None,
                created_at=now,
            )
            db.add(output_record)
            db.flush()
            if item.actual_quantity > 0:
                lot = InventoryLot(
                    household_id=HOUSEHOLD_ID,
                    ingredient_id=None,
                    source_type="RECIPE_OUTPUT",
                    source_id=output_record.id,
                    source_name=f"Recipe output: {row['output_name']}",
                    location_id=item.location_id,
                    quantity=item.actual_quantity,
                    unit_id=row["unit_id"],
                    purchase_date=None,
                    opened_date=None,
                    expiration_date=item.expiration_date,
                    frozen_date=None,
                    thawed_date=None,
                    notes=item.notes.strip() if item.notes else None,
                )
                db.add(lot)
                db.flush()
                transaction = InventoryTransaction(
                    household_id=HOUSEHOLD_ID,
                    lot_id=lot.id,
                    transaction_type="PRODUCTION",
                    quantity_delta=item.actual_quantity,
                    unit_id=row["unit_id"],
                    to_location_id=item.location_id,
                    note=f"Meal completion {completion.id} produced Recipe output {output_record.id}",
                    created_at=now,
                )
                db.add(transaction)
                db.flush()
                output_record.inventory_lot_id = lot.id
                output_record.inventory_transaction_id = transaction.id

        completion.actual_servings_produced = payload.actual_servings_produced
        completion.actual_servings_eaten = payload.actual_servings_eaten
        completion.production_committed_at = now
        completion.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise

    completion = _load_completion(db, planned_meal_id)
    return _read_production(db, planned, completion)