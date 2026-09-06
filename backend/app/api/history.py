from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.completion import MealCompletion
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.production import Leftover, MealCompletionOutput
from app.models.reference import InventoryLocation, MeasurementUnit
from app.schemas.history import InventoryHistoryEntry, MealHistoryEntry

router = APIRouter(prefix="/api/history", tags=["history"])
HOUSEHOLD_ID = 1


def _meal_history_payload(db: Session, completion: MealCompletion) -> dict:
    leftover = db.scalar(select(Leftover).where(Leftover.completion_id == completion.id))
    outputs = list(db.scalars(
        select(MealCompletionOutput)
        .where(MealCompletionOutput.completion_id == completion.id)
        .order_by(MealCompletionOutput.id)
    ))
    allocations_by_usage: dict[int, list] = {}
    for allocation in completion.allocations:
        allocations_by_usage.setdefault(allocation.usage_id, []).append(allocation)

    return {
        "completion_id": completion.id,
        "planned_meal_id": completion.planned_meal_id,
        "meal_name": completion.snapshot_name,
        "finalized_at": completion.finalized_at,
        "production_committed_at": completion.production_committed_at,
        "planned_servings": completion.snapshot_planned_servings,
        "planned_leftover_servings": completion.snapshot_planned_leftover_servings,
        "actual_servings_produced": completion.actual_servings_produced,
        "actual_servings_eaten": completion.actual_servings_eaten,
        "usages": [{
            "recipe_name": usage.recipe_name,
            "planned_ingredient_name": usage.planned_ingredient_name,
            "planned_quantity": usage.planned_quantity,
            "planned_unit_code": usage.planned_unit_code,
            "actual_ingredient_name": usage.actual_ingredient_name,
            "actual_quantity": usage.actual_quantity,
            "actual_unit_code": usage.actual_unit_code,
            "substituted": usage.actual_ingredient_id != usage.planned_ingredient_id,
            "notes": usage.notes,
            "allocations": [{
                "lot_id": allocation.lot_id,
                "inventory_transaction_id": allocation.inventory_transaction_id,
                "source_quantity": allocation.source_quantity,
                "source_unit_code": allocation.source_unit_code,
            } for allocation in allocations_by_usage.get(usage.id, [])],
        } for usage in completion.usages],
        "leftover": None if leftover is None else {
            "id": leftover.id,
            "leftover_servings": leftover.leftover_servings,
            "serving_unit": leftover.serving_unit,
            "expiration_date": leftover.expiration_date,
            "notes": leftover.notes,
            "inventory_lot_id": leftover.inventory_lot_id,
            "created_at": leftover.created_at,
        },
        "outputs": [{
            "id": output.id,
            "recipe_name": output.recipe_name,
            "output_name": output.output_name,
            "actual_quantity": output.actual_quantity,
            "unit_code": output.unit_code,
            "quantity_overridden": output.quantity_overridden,
            "expiration_date": output.expiration_date,
            "notes": output.notes,
            "inventory_lot_id": output.inventory_lot_id,
            "created_at": output.created_at,
        } for output in outputs],
    }


@router.get("/meals", response_model=list[MealHistoryEntry])
def meal_history(db: Session = Depends(get_db)) -> list[dict]:
    completions = list(db.scalars(
        select(MealCompletion)
        .where(MealCompletion.status == "FINALIZED", MealCompletion.finalized_at.is_not(None))
        .options(selectinload(MealCompletion.usages), selectinload(MealCompletion.allocations))
        .order_by(MealCompletion.finalized_at.desc(), MealCompletion.id.desc())
    ))
    return [_meal_history_payload(db, completion) for completion in completions]


@router.get("/inventory", response_model=list[InventoryHistoryEntry])
def inventory_history(
    ingredient_id: int | None = None,
    lot_id: int | None = None,
    transaction_type: str | None = None,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    statement = (
        select(InventoryTransaction)
        .join(InventoryLot, InventoryLot.id == InventoryTransaction.lot_id)
        .where(InventoryTransaction.household_id == HOUSEHOLD_ID, InventoryLot.household_id == HOUSEHOLD_ID)
    )
    if ingredient_id is not None:
        statement = statement.where(InventoryLot.ingredient_id == ingredient_id)
    if lot_id is not None:
        statement = statement.where(InventoryTransaction.lot_id == lot_id)
    if transaction_type:
        statement = statement.where(InventoryTransaction.transaction_type == transaction_type)
    if start_date is not None:
        statement = statement.where(InventoryTransaction.created_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        statement = statement.where(InventoryTransaction.created_at <= datetime.combine(end_date, time.max))

    transactions = list(db.scalars(statement.order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())))
    lot_ids = {row.lot_id for row in transactions}
    lots = {row.id: row for row in db.scalars(select(InventoryLot).where(InventoryLot.id.in_(lot_ids)))} if lot_ids else {}
    ingredient_ids = {lot.ingredient_id for lot in lots.values() if lot.ingredient_id is not None}
    unit_ids = {row.unit_id for row in transactions}
    location_ids = {
        location_id
        for row in transactions
        for location_id in (row.from_location_id, row.to_location_id)
        if location_id is not None
    }
    ingredients = {row.id: row.name for row in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))} if ingredient_ids else {}
    units = {row.id: row.code for row in db.scalars(select(MeasurementUnit).where(MeasurementUnit.id.in_(unit_ids)))} if unit_ids else {}
    locations = {row.id: row.name for row in db.scalars(select(InventoryLocation).where(InventoryLocation.id.in_(location_ids)))} if location_ids else {}

    result: list[dict] = []
    for transaction in transactions:
        lot = lots[transaction.lot_id]
        result.append({
            "transaction_id": transaction.id,
            "created_at": transaction.created_at,
            "transaction_type": transaction.transaction_type,
            "lot_id": transaction.lot_id,
            "ingredient_id": lot.ingredient_id,
            "ingredient_name": ingredients.get(lot.ingredient_id) if lot.ingredient_id is not None else None,
            "source_type": lot.source_type,
            "source_id": lot.source_id,
            "source_name": lot.source_name,
            "quantity_delta": transaction.quantity_delta,
            "unit_id": transaction.unit_id,
            "unit_code": units.get(transaction.unit_id, str(transaction.unit_id)),
            "from_location_id": transaction.from_location_id,
            "from_location_name": locations.get(transaction.from_location_id) if transaction.from_location_id is not None else None,
            "to_location_id": transaction.to_location_id,
            "to_location_name": locations.get(transaction.to_location_id) if transaction.to_location_id is not None else None,
            "note": transaction.note,
        })
    return result
