from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.reference import InventoryLocation, MeasurementUnit
from app.models.reservation import InventoryReservation
from app.services.production_coverage import production_availability_rows

HOUSEHOLD_ID = 1
SOURCE_ORDER = {"INGREDIENT": 0, "LEFTOVER": 1, "RECIPE_OUTPUT": 2}


def _lot_priority(lot: InventoryLot, preferred_location_id: int | None) -> tuple:
    still_frozen = lot.frozen_date is not None and lot.thawed_date is None
    return (
        lot.expiration_date is None,
        lot.expiration_date or date.max,
        lot.opened_date is None,
        still_frozen,
        lot.purchase_date is None,
        lot.purchase_date or date.max,
        preferred_location_id is None or lot.location_id != preferred_location_id,
        lot.id,
    )


def use_soon_rows(db: Session, horizon_days: int = 7, today: date | None = None) -> list[dict]:
    today = today or date.today()
    cutoff = today + timedelta(days=horizon_days)
    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    locations = {row.id: row for row in db.scalars(select(InventoryLocation).where(InventoryLocation.household_id == HOUSEHOLD_ID))}
    ingredients = {row.id: row for row in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))}

    ingredient_lots = list(db.scalars(
        select(InventoryLot).where(
            InventoryLot.household_id == HOUSEHOLD_ID,
            InventoryLot.source_type == "INGREDIENT",
            InventoryLot.quantity > 0,
        )
    ))

    grouped: dict[tuple[int, str], list[InventoryLot]] = defaultdict(list)
    for lot in ingredient_lots:
        unit = units.get(lot.unit_id)
        if lot.ingredient_id is None or unit is None:
            continue
        grouped[(lot.ingredient_id, unit.unit_family)].append(lot)

    ingredient_available: dict[int, Decimal] = {}
    for (ingredient_id, family), lots in grouped.items():
        ingredient = ingredients.get(ingredient_id)
        if ingredient is None:
            continue
        remaining_by_lot = {
            lot.id: (
                Decimal("0")
                if lot.expiration_date is not None and lot.expiration_date < today
                else Decimal(lot.quantity) * Decimal(units[lot.unit_id].base_multiplier)
            )
            for lot in lots
        }
        reserved_base = Decimal("0")
        for reservation in db.scalars(select(InventoryReservation).where(
            InventoryReservation.household_id == HOUSEHOLD_ID,
            InventoryReservation.ingredient_id == ingredient_id,
            InventoryReservation.status == "ACTIVE",
        )):
            unit = units.get(reservation.unit_id)
            if unit is not None and unit.unit_family == family:
                reserved_base += Decimal(reservation.quantity) * Decimal(unit.base_multiplier)

        remaining_reservation = reserved_base
        for lot in sorted(lots, key=lambda row: _lot_priority(row, ingredient.default_location_id)):
            if remaining_reservation <= 0:
                break
            claimed = min(remaining_by_lot[lot.id], remaining_reservation)
            remaining_by_lot[lot.id] -= claimed
            remaining_reservation -= claimed

        for lot in lots:
            unit = units[lot.unit_id]
            ingredient_available[lot.id] = remaining_by_lot[lot.id] / Decimal(unit.base_multiplier)

    rows: list[dict] = []
    for lot in ingredient_lots:
        if lot.expiration_date is None or lot.expiration_date < today or lot.expiration_date > cutoff:
            continue
        available = ingredient_available.get(lot.id, Decimal("0"))
        if available <= 0:
            continue
        ingredient = ingredients.get(lot.ingredient_id or -1)
        unit = units.get(lot.unit_id)
        location = locations.get(lot.location_id)
        if ingredient is None or unit is None or location is None:
            continue
        rows.append({
            "lot_id": lot.id,
            "source_type": "INGREDIENT",
            "source_id": lot.ingredient_id,
            "source_name": ingredient.name,
            "ingredient_id": lot.ingredient_id,
            "location_id": lot.location_id,
            "location_name": location.name,
            "available_quantity": available,
            "unit_id": lot.unit_id,
            "unit_code": unit.code,
            "expiration_date": lot.expiration_date,
            "days_remaining": (lot.expiration_date - today).days,
        })

    produced_by_lot = {row["lot_id"]: row for row in production_availability_rows(db)}
    produced_lots = list(db.scalars(select(InventoryLot).where(
        InventoryLot.household_id == HOUSEHOLD_ID,
        InventoryLot.source_type.in_(["LEFTOVER", "RECIPE_OUTPUT"]),
        InventoryLot.quantity > 0,
    )))
    for lot in produced_lots:
        if lot.expiration_date is None or lot.expiration_date < today or lot.expiration_date > cutoff:
            continue
        availability = produced_by_lot.get(lot.id)
        if availability is None:
            continue
        available = Decimal(availability["available_quantity"])
        if available <= 0:
            continue
        unit = units.get(lot.unit_id)
        location = locations.get(lot.location_id)
        if unit is None or location is None:
            continue
        rows.append({
            "lot_id": lot.id,
            "source_type": lot.source_type,
            "source_id": lot.source_id,
            "source_name": lot.source_name or f"{lot.source_type} {lot.source_id}",
            "ingredient_id": None,
            "location_id": lot.location_id,
            "location_name": location.name,
            "available_quantity": available,
            "unit_id": lot.unit_id,
            "unit_code": unit.code,
            "expiration_date": lot.expiration_date,
            "days_remaining": (lot.expiration_date - today).days,
        })

    rows.sort(key=lambda row: (
        row["days_remaining"],
        row["expiration_date"],
        SOURCE_ORDER.get(row["source_type"], 99),
        row["lot_id"],
    ))
    return rows
