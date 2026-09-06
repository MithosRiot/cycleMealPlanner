from datetime import datetime
from decimal import Decimal
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.completion import MealCompletion
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.schemas.planned_meal import NonFoodOccurrenceAssign, PlannedMealRead

router = APIRouter(prefix="/api/meal-cycles", tags=["meal-placement"])
HOUSEHOLD_ID = 1


def _load_slot(db: Session, cycle_id: int, slot_id: int) -> CycleSlot:
    slot = db.scalar(
        select(CycleSlot)
        .join(MealCycle)
        .where(
            CycleSlot.id == slot_id,
            CycleSlot.cycle_id == cycle_id,
            MealCycle.household_id == HOUSEHOLD_ID,
        )
        .options(selectinload(CycleSlot.cycle), selectinload(CycleSlot.planned_meal))
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Cycle slot not found")
    if slot.cycle.status != "DRAFT":
        raise HTTPException(status_code=409, detail=f"Cannot edit placements in a {slot.cycle.status} Meal Cycle")
    return slot


def _display_name(payload: NonFoodOccurrenceAssign) -> str:
    if payload.occurrence_type == "SKIPPED":
        return "Skipped meal"
    if payload.occurrence_type == "EATING_OUT":
        return payload.title or "Eating out"
    return payload.title or "Manual entry"


def _completion_fingerprint(planned: PlannedMeal) -> str:
    raw = json.dumps(
        {
            "source_type": planned.source_type,
            "snapshot_name": planned.snapshot_name,
            "snapshot_description": planned.snapshot_description,
            "scaled_components": [],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.post(
    "/{cycle_id}/slots/{slot_id}/planned-occurrence",
    response_model=PlannedMealRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_non_food_occurrence(
    cycle_id: int,
    slot_id: int,
    payload: NonFoodOccurrenceAssign,
    db: Session = Depends(get_db),
) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    if slot.planned_meal is not None:
        if slot.planned_meal.locked:
            raise HTTPException(status_code=409, detail="Placement is locked")
        db.delete(slot.planned_meal)
        db.flush()

    planned = PlannedMeal(
        cycle_slot_id=slot.id,
        meal_id=None,
        source_type=payload.occurrence_type,
        source_recipe_id=None,
        source_origin_planned_meal_id=None,
        source_record_id=None,
        source_recipe_output_id=None,
        source_quantity=None,
        source_unit_id=None,
        locked=False,
        planned_servings=Decimal("1"),
        planned_leftover_servings=Decimal("0"),
        component_serving_overrides="{}",
        scaled_components="[]",
        snapshot_name=_display_name(payload),
        snapshot_description=payload.notes,
        snapshot_meal_types="[]",
        snapshot_components="[]",
    )
    db.add(planned)
    db.flush()

    now = datetime.utcnow()
    db.add(
        MealCompletion(
            planned_meal_id=planned.id,
            status="FINALIZED",
            plan_fingerprint=_completion_fingerprint(planned),
            snapshot_name=planned.snapshot_name,
            snapshot_planned_servings=Decimal("0"),
            snapshot_planned_leftover_servings=Decimal("0"),
            snapshot_scaled_components="[]",
            created_at=now,
            updated_at=now,
            finalized_at=now,
            actual_servings_produced=Decimal("0"),
            actual_servings_eaten=Decimal("0"),
        )
    )
    db.commit()
    db.refresh(planned)
    return planned
