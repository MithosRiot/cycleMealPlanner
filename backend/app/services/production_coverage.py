from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.completion import MealCompletion
from app.models.inventory import InventoryLot
from app.models.meal_cycle import CycleSlot
from app.models.planned_meal import PlannedMeal
from app.models.production import Leftover, MealCompletionOutput
from app.models.production_coverage import ProductionCoverageReservation
from app.models.reservation import InventoryReservation

HOUSEHOLD_ID = 1
TOLERANCE = Decimal("0.000001")


def release_source_ingredient_reservations(db: Session, planned_meal_id: int) -> int:
    rows = list(db.scalars(
        select(InventoryReservation).where(
            InventoryReservation.household_id == HOUSEHOLD_ID,
            InventoryReservation.planned_meal_id == planned_meal_id,
            InventoryReservation.status == "ACTIVE",
        )
    ))
    for row in rows:
        row.status = "RELEASED"
    return len(rows)


def release_coverage_for_planned(db: Session, planned_meal_id: int, reason: str = "REMOVED") -> int:
    now = datetime.utcnow()
    rows = list(db.scalars(
        select(ProductionCoverageReservation).where(
            ProductionCoverageReservation.planned_meal_id == planned_meal_id,
            ProductionCoverageReservation.status == "ACTIVE",
        )
    ))
    for row in rows:
        row.status = "RELEASED"
        row.release_reason = reason
        row.released_at = now
        row.updated_at = now
    return len(rows)


def _resolve_source(db: Session, planned: PlannedMeal) -> tuple[int | None, InventoryLot | None]:
    if planned.source_type == "LEFTOVER":
        leftover = None
        if planned.source_record_id is not None:
            candidate = db.get(Leftover, planned.source_record_id)
            if candidate is not None and candidate.planned_meal_id == planned.source_origin_planned_meal_id:
                leftover = candidate
        if leftover is None:
            leftover = db.scalar(
                select(Leftover)
                .where(Leftover.planned_meal_id == planned.source_origin_planned_meal_id)
                .order_by(Leftover.id)
            )
        lot = db.get(InventoryLot, leftover.inventory_lot_id) if leftover and leftover.inventory_lot_id else None
        return (leftover.id if leftover else None), lot

    if planned.source_type == "RECIPE_OUTPUT":
        statement = (
            select(MealCompletionOutput)
            .join(MealCompletion, MealCompletion.id == MealCompletionOutput.completion_id)
            .where(MealCompletion.planned_meal_id == planned.source_origin_planned_meal_id)
        )
        if planned.source_record_id is not None:
            statement = statement.where(MealCompletionOutput.id == planned.source_record_id)
        elif planned.source_recipe_output_id is not None:
            statement = statement.where(MealCompletionOutput.recipe_output_id == planned.source_recipe_output_id)
        output = db.scalar(statement.order_by(MealCompletionOutput.id))
        lot = db.get(InventoryLot, output.inventory_lot_id) if output and output.inventory_lot_id else None
        return (output.id if output else None), lot

    return None, None


def _placement_sort_key(planned: PlannedMeal) -> tuple:
    slot = planned.cycle_slot
    cycle = slot.cycle
    scheduled = slot.scheduled_datetime
    return (
        scheduled is None,
        scheduled.isoformat() if scheduled is not None else "",
        cycle.id,
        slot.day_number,
        slot.sort_order,
        planned.id,
    )


def reconcile_production_coverage(db: Session) -> list[ProductionCoverageReservation]:
    placements = list(db.scalars(
        select(PlannedMeal)
        .where(PlannedMeal.source_type.in_(["LEFTOVER", "RECIPE_OUTPUT"]))
        .options(
            selectinload(PlannedMeal.cycle_slot).selectinload(CycleSlot.cycle),
            selectinload(PlannedMeal.cycle_slot).selectinload(CycleSlot.slot_definition),
        )
    ))
    placements.sort(key=_placement_sort_key)
    placement_ids = {row.id for row in placements}

    active_rows = list(db.scalars(
        select(ProductionCoverageReservation)
        .where(ProductionCoverageReservation.status == "ACTIVE")
        .order_by(ProductionCoverageReservation.id)
    ))
    by_planned: dict[int, list[ProductionCoverageReservation]] = {}
    now = datetime.utcnow()
    for row in active_rows:
        by_planned.setdefault(row.planned_meal_id, []).append(row)
        if row.planned_meal_id not in placement_ids:
            row.status = "RELEASED"
            row.release_reason = "REMOVED"
            row.released_at = now
            row.updated_at = now

    remaining_by_lot: dict[int, Decimal] = {}
    result: list[ProductionCoverageReservation] = []

    for planned in placements:
        requested = Decimal(planned.source_quantity or 0)
        if requested <= 0 or planned.source_unit_id is None or planned.source_origin_planned_meal_id is None:
            continue

        source_record_id, lot = _resolve_source(db, planned)
        valid_lot = lot is not None and lot.quantity > 0 and lot.unit_id == planned.source_unit_id
        if valid_lot and planned.scheduled_date is not None and lot.expiration_date is not None and lot.expiration_date < planned.scheduled_date:
            valid_lot = False

        existing = next((row for row in by_planned.get(planned.id, []) if row.status == "ACTIVE"), None)
        identity_matches = bool(existing and (
            existing.source_type == planned.source_type
            and existing.source_origin_planned_meal_id == planned.source_origin_planned_meal_id
            and existing.source_recipe_output_id == planned.source_recipe_output_id
            and existing.unit_id == planned.source_unit_id
            and Decimal(existing.requested_quantity) == requested
            and existing.cycle_slot_id == planned.cycle_slot_id
        ))
        if existing is not None and not identity_matches:
            existing.status = "RELEASED"
            existing.release_reason = "REPLACED"
            existing.released_at = now
            existing.updated_at = now
            existing = None

        if valid_lot:
            remaining = remaining_by_lot.setdefault(lot.id, Decimal(lot.quantity))
            reserved = min(requested, max(remaining, Decimal("0")))
            remaining_by_lot[lot.id] = remaining - reserved
        else:
            reserved = Decimal("0")
        shortage = max(requested - reserved, Decimal("0"))

        if existing is None:
            existing = ProductionCoverageReservation(
                household_id=HOUSEHOLD_ID,
                cycle_id=planned.cycle_slot.cycle_id,
                planned_meal_id=planned.id,
                cycle_slot_id=planned.cycle_slot_id,
                source_origin_planned_meal_id=planned.source_origin_planned_meal_id,
                source_type=planned.source_type,
                source_record_id=source_record_id,
                source_recipe_output_id=planned.source_recipe_output_id,
                lot_id=lot.id if valid_lot else None,
                requested_quantity=requested,
                reserved_quantity=reserved,
                shortage_quantity=shortage,
                unit_id=planned.source_unit_id,
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(existing)
        else:
            existing.source_record_id = source_record_id
            existing.lot_id = lot.id if valid_lot else None
            existing.reserved_quantity = reserved
            existing.shortage_quantity = shortage
            existing.release_reason = None
            existing.released_at = None
            existing.updated_at = now
        result.append(existing)

    return result


def reserved_for_lot(db: Session, lot_id: int) -> Decimal:
    rows = db.scalars(
        select(ProductionCoverageReservation.reserved_quantity).where(
            ProductionCoverageReservation.lot_id == lot_id,
            ProductionCoverageReservation.status == "ACTIVE",
        )
    )
    return sum((Decimal(value) for value in rows), Decimal("0"))


def production_availability_rows(db: Session) -> list[dict]:
    lots = list(db.scalars(
        select(InventoryLot)
        .where(
            InventoryLot.household_id == HOUSEHOLD_ID,
            InventoryLot.source_type.in_(["LEFTOVER", "RECIPE_OUTPUT"]),
        )
        .order_by(InventoryLot.id)
    ))
    rows = []
    for lot in lots:
        physical = Decimal(lot.quantity)
        reserved = reserved_for_lot(db, lot.id)
        rows.append({
            "lot_id": lot.id,
            "source_type": lot.source_type,
            "source_id": lot.source_id,
            "source_name": lot.source_name,
            "unit_id": lot.unit_id,
            "physical_quantity": physical,
            "reserved_quantity": reserved,
            "available_quantity": max(physical - reserved, Decimal("0")),
            "expiration_date": lot.expiration_date,
        })
    return rows


def coverage_summary_for_origin(db: Session, source_origin_planned_meal_id: int) -> dict:
    rows = list(db.scalars(
        select(ProductionCoverageReservation).where(
            ProductionCoverageReservation.source_origin_planned_meal_id == source_origin_planned_meal_id,
            ProductionCoverageReservation.status == "ACTIVE",
        )
    ))
    return {
        "reservation_count": len(rows),
        "reserved_quantity": sum((Decimal(row.reserved_quantity) for row in rows), Decimal("0")),
        "shortage_quantity": sum((Decimal(row.shortage_quantity) for row in rows), Decimal("0")),
    }
