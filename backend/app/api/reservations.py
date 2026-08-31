import json
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.inventory import InventoryLot
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.reference import MeasurementUnit
from app.models.reservation import InventoryReservation
from app.schemas.reservation import InventoryAvailabilityRead, ReservationCycleSummary
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(tags=["reservations"])
HOUSEHOLD_ID = 1


def _cycle(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(select(MealCycle).where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _requirements(db: Session, cycle_id: int) -> list[dict]:
    rows = db.execute(
        select(PlannedMeal.id, PlannedMeal.scaled_components)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .where(CycleSlot.cycle_id == cycle_id)
    ).all()
    required: list[dict] = []
    for planned_meal_id, raw in rows:
        try:
            components = json.loads(raw or "[]")
        except json.JSONDecodeError:
            components = []
        for component in components:
            meal_recipe_id = int(component.get("meal_recipe_id")) if component.get("meal_recipe_id") is not None else None
            recipe_id = int(component["recipe_id"])
            for ingredient in component.get("ingredients", []):
                quantity = Decimal(str(ingredient.get("quantity", "0")))
                if quantity <= 0:
                    continue
                required.append({
                    "planned_meal_id": int(planned_meal_id),
                    "meal_recipe_id": meal_recipe_id,
                    "recipe_id": recipe_id,
                    "recipe_ingredient_id": int(ingredient["recipe_ingredient_id"]) if ingredient.get("recipe_ingredient_id") is not None else None,
                    "ingredient_id": int(ingredient["ingredient_id"]),
                    "quantity": quantity,
                    "unit_id": int(ingredient["unit_id"]),
                })
    return required


def _key(row: dict | InventoryReservation) -> tuple[int, int | None, int | None]:
    if isinstance(row, InventoryReservation):
        return row.planned_meal_id, row.meal_recipe_id, row.recipe_ingredient_id
    return row["planned_meal_id"], row["meal_recipe_id"], row["recipe_ingredient_id"]


def _summary(db: Session, cycle_id: int) -> ReservationCycleSummary:
    reservations = list(db.scalars(select(InventoryReservation).where(InventoryReservation.cycle_id == cycle_id).order_by(InventoryReservation.id)))
    return ReservationCycleSummary(
        cycle_id=cycle_id,
        active_count=sum(1 for row in reservations if row.status == "ACTIVE"),
        released_count=sum(1 for row in reservations if row.status == "RELEASED"),
        reservations=reservations,
    )


@router.get("/api/meal-cycles/{cycle_id}/reservations", response_model=ReservationCycleSummary)
def get_cycle_reservations(cycle_id: int, db: Session = Depends(get_db)) -> ReservationCycleSummary:
    _cycle(db, cycle_id)
    return _summary(db, cycle_id)


@router.post("/api/meal-cycles/{cycle_id}/reservations/regenerate", response_model=ReservationCycleSummary)
def regenerate_cycle_reservations(cycle_id: int, db: Session = Depends(get_db)) -> ReservationCycleSummary:
    _cycle(db, cycle_id)
    requirements = _requirements(db, cycle_id)
    existing = list(db.scalars(select(InventoryReservation).where(InventoryReservation.cycle_id == cycle_id)))
    existing_by_key = {_key(row): row for row in existing}
    seen: set[tuple[int, int | None, int | None]] = set()

    for requirement in requirements:
        key = _key(requirement)
        seen.add(key)
        model = existing_by_key.get(key)
        if model is None:
            model = InventoryReservation(
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
            )
            db.add(model)
        else:
            model.recipe_id = requirement["recipe_id"]
            model.ingredient_id = requirement["ingredient_id"]
            model.quantity = requirement["quantity"]
            model.unit_id = requirement["unit_id"]
            model.status = "ACTIVE"

    for model in existing:
        if _key(model) not in seen and model.status == "ACTIVE":
            model.status = "RELEASED"

    db.commit()
    return _summary(db, cycle_id)


@router.get("/api/inventory/availability", response_model=list[InventoryAvailabilityRead])
def inventory_availability(db: Session = Depends(get_db)) -> list[InventoryAvailabilityRead]:
    units = {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    lots = list(db.scalars(select(InventoryLot).where(InventoryLot.household_id == HOUSEHOLD_ID, InventoryLot.quantity > 0)))
    reservations = list(db.scalars(select(InventoryReservation).where(InventoryReservation.household_id == HOUSEHOLD_ID, InventoryReservation.status == "ACTIVE")))

    grouped_lots: dict[tuple[int, str], list[InventoryLot]] = defaultdict(list)
    grouped_reservations: dict[tuple[int, str], list[InventoryReservation]] = defaultdict(list)
    for lot in lots:
        unit = units.get(lot.unit_id)
        if unit is not None:
            grouped_lots[(lot.ingredient_id, unit.unit_family)].append(lot)
    for reservation in reservations:
        unit = units.get(reservation.unit_id)
        if unit is not None:
            grouped_reservations[(reservation.ingredient_id, unit.unit_family)].append(reservation)

    result: list[InventoryAvailabilityRead] = []
    for key in sorted(set(grouped_lots) | set(grouped_reservations)):
        lot_rows = grouped_lots.get(key, [])
        reservation_rows = grouped_reservations.get(key, [])
        reference_unit_id = lot_rows[0].unit_id if lot_rows else reservation_rows[0].unit_id
        reference_unit = units[reference_unit_id]
        physical = Decimal("0")
        reserved = Decimal("0")
        for lot in lot_rows:
            try:
                physical += convert_quantity(Decimal(lot.quantity), units[lot.unit_id], reference_unit)
            except UnitConversionError:
                continue
        for reservation in reservation_rows:
            try:
                reserved += convert_quantity(Decimal(reservation.quantity), units[reservation.unit_id], reference_unit)
            except UnitConversionError:
                continue
        available = max(Decimal("0"), physical - reserved)
        shortage = max(Decimal("0"), reserved - physical)
        result.append(InventoryAvailabilityRead(
            ingredient_id=key[0],
            unit_family=key[1],
            unit_id=reference_unit.id,
            unit_code=reference_unit.code,
            physical_quantity=physical,
            reserved_quantity=reserved,
            available_quantity=available,
            shortage_quantity=shortage,
        ))
    return result
