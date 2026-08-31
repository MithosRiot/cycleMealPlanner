from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.reference import InventoryLocation, MeasurementUnit
from app.models.reservation import InventoryReservation

HOUSEHOLD_ID = 1


@dataclass
class LotState:
    lot: InventoryLot
    unit: MeasurementUnit
    location: InventoryLocation | None
    remaining_base: Decimal


def _lot_sort_key(state: LotState, preferred_location_id: int | None) -> tuple:
    lot = state.lot
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


def _load_states(
    db: Session,
    ingredient_id: int,
    family: str,
    units: dict[int, MeasurementUnit],
) -> list[LotState]:
    locations = {row.id: row for row in db.scalars(select(InventoryLocation).where(InventoryLocation.household_id == HOUSEHOLD_ID))}
    states: list[LotState] = []
    for lot in db.scalars(
        select(InventoryLot).where(
            InventoryLot.household_id == HOUSEHOLD_ID,
            InventoryLot.ingredient_id == ingredient_id,
            InventoryLot.quantity > 0,
        )
    ):
        unit = units.get(lot.unit_id)
        if unit is None or unit.unit_family != family:
            continue
        states.append(
            LotState(
                lot=lot,
                unit=unit,
                location=locations.get(lot.location_id),
                remaining_base=Decimal(lot.quantity) * Decimal(unit.base_multiplier),
            )
        )
    return states


def _consume_other_reservations(
    db: Session,
    states: list[LotState],
    ingredient_id: int,
    family: str,
    units: dict[int, MeasurementUnit],
    preferred_location_id: int | None,
    use_date: date | None,
    exclude_cycle_id: int | None,
) -> Decimal:
    stmt = select(InventoryReservation).where(
        InventoryReservation.household_id == HOUSEHOLD_ID,
        InventoryReservation.ingredient_id == ingredient_id,
        InventoryReservation.status == "ACTIVE",
    )
    if exclude_cycle_id is not None:
        stmt = stmt.where(InventoryReservation.cycle_id != exclude_cycle_id)

    reserved_base = Decimal("0")
    for reservation in db.scalars(stmt):
        unit = units.get(reservation.unit_id)
        if unit is not None and unit.unit_family == family:
            reserved_base += Decimal(reservation.quantity) * Decimal(unit.base_multiplier)

    remaining = reserved_base
    eligible = [
        state for state in states
        if use_date is None or state.lot.expiration_date is None or state.lot.expiration_date >= use_date
    ]
    for state in sorted(eligible, key=lambda row: _lot_sort_key(row, preferred_location_id)):
        if remaining <= 0:
            break
        claimed = min(state.remaining_base, remaining)
        state.remaining_base -= claimed
        remaining -= claimed
    return reserved_base


def allocate_requirement(
    db: Session,
    *,
    ingredient: Ingredient,
    quantity: Decimal,
    target_unit: MeasurementUnit,
    use_date: date | None = None,
    exclude_cycle_id: int | None = None,
    states: list[LotState] | None = None,
    consume_other_reservations: bool = True,
    units: dict[int, MeasurementUnit] | None = None,
) -> dict:
    if quantity <= 0:
        raise ValueError("Allocation quantity must be positive")
    units = units or {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    family = target_unit.unit_family
    states = states if states is not None else _load_states(db, ingredient.id, family, units)

    reserved_elsewhere_base = Decimal("0")
    if consume_other_reservations:
        reserved_elsewhere_base = _consume_other_reservations(
            db,
            states,
            ingredient.id,
            family,
            units,
            ingredient.default_location_id,
            use_date,
            exclude_cycle_id,
        )

    required_base = quantity * Decimal(target_unit.base_multiplier)
    remaining_base = required_base
    allocations: list[dict] = []
    eligible = [
        state for state in states
        if state.remaining_base > 0
        and (use_date is None or state.lot.expiration_date is None or state.lot.expiration_date >= use_date)
    ]
    for state in sorted(eligible, key=lambda row: _lot_sort_key(row, ingredient.default_location_id)):
        if remaining_base <= 0:
            break
        allocated_base = min(state.remaining_base, remaining_base)
        state.remaining_base -= allocated_base
        remaining_base -= allocated_base
        allocations.append(
            {
                "lot_id": state.lot.id,
                "allocated_quantity": allocated_base / Decimal(target_unit.base_multiplier),
                "unit_id": target_unit.id,
                "unit_code": target_unit.code,
                "source_quantity": state.lot.quantity,
                "source_unit_id": state.unit.id,
                "source_unit_code": state.unit.code,
                "location_id": state.lot.location_id,
                "location_name": state.location.name if state.location else None,
                "purchase_date": state.lot.purchase_date,
                "opened_date": state.lot.opened_date,
                "expiration_date": state.lot.expiration_date,
                "frozen_date": state.lot.frozen_date,
                "thawed_date": state.lot.thawed_date,
            }
        )

    return {
        "ingredient_id": ingredient.id,
        "requested_quantity": quantity,
        "unit_id": target_unit.id,
        "unit_code": target_unit.code,
        "unit_family": family,
        "use_date": use_date,
        "reserved_elsewhere_quantity": reserved_elsewhere_base / Decimal(target_unit.base_multiplier),
        "allocated_quantity": (required_base - remaining_base) / Decimal(target_unit.base_multiplier),
        "shortage_quantity": max(remaining_base / Decimal(target_unit.base_multiplier), Decimal("0")),
        "allocations": allocations,
    }


def allocate_requirement_sequence(db: Session, requirements: list[dict], *, exclude_cycle_id: int | None = None) -> list[dict]:
    units = {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    ingredients = {
        ingredient.id: ingredient
        for ingredient in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    state_cache: dict[tuple[int, str], list[LotState]] = {}
    reservation_consumed: set[tuple[int, str]] = set()
    results: list[dict] = []

    for requirement in requirements:
        ingredient_id = int(requirement["ingredient_id"])
        unit_id = int(requirement["unit_id"])
        target_unit = units.get(unit_id)
        ingredient = ingredients.get(ingredient_id)
        if target_unit is None or ingredient is None:
            continue
        key = (ingredient_id, target_unit.unit_family)
        states = state_cache.setdefault(key, _load_states(db, ingredient_id, target_unit.unit_family, units))
        result = allocate_requirement(
            db,
            ingredient=ingredient,
            quantity=Decimal(str(requirement["quantity"])),
            target_unit=target_unit,
            use_date=requirement.get("use_date"),
            exclude_cycle_id=exclude_cycle_id,
            states=states,
            consume_other_reservations=key not in reservation_consumed,
            units=units,
        )
        reservation_consumed.add(key)
        results.append({**requirement, **result})
    return results
