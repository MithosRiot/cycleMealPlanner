from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import InventoryLot
from app.models.reference import MeasurementUnit
from app.models.reservation import InventoryReservation
from app.services.units import UnitConversionError, convert_quantity

HOUSEHOLD_ID = 1


def unit_map(db: Session) -> dict[int, MeasurementUnit]:
    return {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}


def availability_for(
    db: Session,
    ingredient_id: int,
    unit_family: str,
    target_unit: MeasurementUnit,
    *,
    exclude_cycle_id: int | None = None,
    units: dict[int, MeasurementUnit] | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    units = units or unit_map(db)
    physical = Decimal("0")
    reserved = Decimal("0")

    lots = db.scalars(
        select(InventoryLot).where(
            InventoryLot.household_id == HOUSEHOLD_ID,
            InventoryLot.ingredient_id == ingredient_id,
            InventoryLot.quantity > 0,
        )
    )
    for lot in lots:
        source = units.get(lot.unit_id)
        if source is None or source.unit_family != unit_family:
            continue
        try:
            physical += convert_quantity(Decimal(lot.quantity), source, target_unit)
        except UnitConversionError:
            continue

    reservation_stmt = select(InventoryReservation).where(
        InventoryReservation.household_id == HOUSEHOLD_ID,
        InventoryReservation.ingredient_id == ingredient_id,
        InventoryReservation.status == "ACTIVE",
    )
    if exclude_cycle_id is not None:
        reservation_stmt = reservation_stmt.where(InventoryReservation.cycle_id != exclude_cycle_id)

    for reservation in db.scalars(reservation_stmt):
        source = units.get(reservation.unit_id)
        if source is None or source.unit_family != unit_family:
            continue
        try:
            reserved += convert_quantity(Decimal(reservation.quantity), source, target_unit)
        except UnitConversionError:
            continue

    available = max(physical - reserved, Decimal("0"))
    shortage = max(reserved - physical, Decimal("0"))
    return physical, reserved, available, shortage


def availability_rows(db: Session) -> list[dict]:
    units = unit_map(db)
    families: dict[tuple[int, str], set[int]] = defaultdict(set)

    for lot in db.scalars(select(InventoryLot).where(InventoryLot.household_id == HOUSEHOLD_ID, InventoryLot.quantity > 0)):
        unit = units.get(lot.unit_id)
        if unit is not None:
            families[(lot.ingredient_id, unit.unit_family)].add(lot.unit_id)

    for reservation in db.scalars(
        select(InventoryReservation).where(
            InventoryReservation.household_id == HOUSEHOLD_ID,
            InventoryReservation.status == "ACTIVE",
        )
    ):
        unit = units.get(reservation.unit_id)
        if unit is not None:
            families[(reservation.ingredient_id, unit.unit_family)].add(reservation.unit_id)

    rows = []
    for (ingredient_id, family), unit_ids in sorted(families.items()):
        target = units[min(unit_ids)]
        physical, reserved, available, shortage = availability_for(
            db, ingredient_id, family, target, units=units
        )
        rows.append({
            "ingredient_id": ingredient_id,
            "unit_family": family,
            "unit_id": target.id,
            "unit_code": target.code,
            "physical_quantity": physical,
            "reserved_quantity": reserved,
            "available_quantity": available,
            "shortage_quantity": shortage,
        })
    return rows
