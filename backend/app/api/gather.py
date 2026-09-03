from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.gather import GatherLotSelection
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.reference import InventoryLocation, MeasurementUnit
from app.schemas.gather import GatherCycleRead, GatherRequirementUpdate
from app.services.inventory_allocation import _consume_other_reservations, _load_states, allocate_requirement_sequence

router = APIRouter(tags=["gather"])
HOUSEHOLD_ID = 1
TOLERANCE = Decimal("0.000001")


def _cycle_or_404(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(
            selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal),
            selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition),
        )
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _requirements(cycle: MealCycle) -> list[dict]:
    rows: list[dict] = []
    for slot in sorted(cycle.slots, key=lambda item: (item.day_number, item.sort_order, item.id)):
        planned = slot.planned_meal
        if planned is None:
            continue
        use_date = cycle.start_date + timedelta(days=slot.day_number - 1) if cycle.start_date else None
        try:
            components = json.loads(planned.scaled_components or "[]")
        except json.JSONDecodeError:
            components = []
        for component in components:
            meal_recipe_id = int(component.get("meal_recipe_id") or 0)
            recipe_id = int(component["recipe_id"])
            for ingredient in component.get("ingredients", []):
                quantity = Decimal(str(ingredient.get("quantity", "0")))
                recipe_ingredient_id = ingredient.get("recipe_ingredient_id")
                if quantity <= 0 or recipe_ingredient_id is None:
                    continue
                rows.append({
                    "planned_meal_id": planned.id,
                    "meal_name": planned.snapshot_name,
                    "day_number": slot.day_number,
                    "slot_label": slot.slot_definition.label,
                    "meal_recipe_id": meal_recipe_id,
                    "recipe_id": recipe_id,
                    "recipe_ingredient_id": int(recipe_ingredient_id),
                    "ingredient_id": int(ingredient["ingredient_id"]),
                    "quantity": quantity,
                    "unit_id": int(ingredient["unit_id"]),
                    "use_date": use_date,
                })
    return rows


def _key(row: dict) -> tuple[int, int, int]:
    return (row["planned_meal_id"], row["meal_recipe_id"], row["recipe_ingredient_id"])


def _lot_capacity_base(db: Session, cycle: MealCycle, requirement: dict, units: dict[int, MeasurementUnit]) -> dict[int, Decimal]:
    target_unit = units[requirement["unit_id"]]
    ingredient = db.get(Ingredient, requirement["ingredient_id"])
    states = _load_states(db, requirement["ingredient_id"], target_unit.unit_family, units)
    _consume_other_reservations(
        db, states, requirement["ingredient_id"], target_unit.unit_family, units,
        ingredient.default_location_id if ingredient else None, requirement["use_date"], cycle.id,
    )
    capacity = {state.lot.id: state.remaining_base for state in states}
    current_key = _key(requirement)
    selections = db.scalars(select(GatherLotSelection).where(GatherLotSelection.ingredient_id == requirement["ingredient_id"]))
    for selection in selections:
        if (selection.planned_meal_id, selection.meal_recipe_id, selection.recipe_ingredient_id) == current_key:
            continue
        unit = units.get(selection.unit_id)
        if unit and unit.unit_family == target_unit.unit_family:
            capacity[selection.lot_id] = max(Decimal("0"), capacity.get(selection.lot_id, Decimal("0")) - Decimal(selection.quantity) * Decimal(unit.base_multiplier))
    return capacity


def _lot_payload(lot: InventoryLot, unit: MeasurementUnit, location: InventoryLocation | None, quantity: Decimal) -> dict:
    return {
        "lot_id": lot.id, "quantity": quantity, "unit_id": unit.id, "unit_code": unit.code,
        "location_id": lot.location_id, "location_name": location.name if location else None,
        "expiration_date": lot.expiration_date, "opened_date": lot.opened_date,
        "frozen_date": lot.frozen_date, "thawed_date": lot.thawed_date,
    }


def _build_cycle(db: Session, cycle: MealCycle) -> dict:
    requirements = _requirements(cycle)
    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    ingredients = {row.id: row for row in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))}
    locations = {row.id: row for row in db.scalars(select(InventoryLocation).where(InventoryLocation.household_id == HOUSEHOLD_ID))}
    lots = {row.id: row for row in db.scalars(select(InventoryLot).where(InventoryLot.household_id == HOUSEHOLD_ID))}
    saved = list(db.scalars(select(GatherLotSelection)))
    saved_by_key: dict[tuple[int, int, int], list[GatherLotSelection]] = {}
    for row in saved:
        saved_by_key.setdefault((row.planned_meal_id, row.meal_recipe_id, row.recipe_ingredient_id), []).append(row)

    allocations = allocate_requirement_sequence(db, requirements, exclude_cycle_id=cycle.id)
    allocation_by_key = {_key(row): row for row in allocations}
    output: list[dict] = []
    for requirement in requirements:
        target_unit = units.get(requirement["unit_id"])
        ingredient = ingredients.get(requirement["ingredient_id"])
        if target_unit is None or ingredient is None:
            continue
        capacity = _lot_capacity_base(db, cycle, requirement, units)
        selections: list[dict] = []
        selected_base = Decimal("0")
        for selected in saved_by_key.get(_key(requirement), []):
            lot = lots.get(selected.lot_id); unit = units.get(selected.unit_id)
            if lot is None or unit is None:
                continue
            selected_base += Decimal(selected.quantity) * Decimal(unit.base_multiplier)
            selections.append(_lot_payload(lot, unit, locations.get(lot.location_id), Decimal(selected.quantity)))

        suggestions: list[dict] = []
        for allocation in allocation_by_key.get(_key(requirement), {}).get("allocations", []):
            lot = lots.get(allocation["lot_id"])
            if lot is None:
                continue
            lot_unit = units[lot.unit_id]
            base = Decimal(str(allocation["allocated_quantity"])) * Decimal(target_unit.base_multiplier)
            suggestions.append(_lot_payload(lot, lot_unit, locations.get(lot.location_id), base / Decimal(lot_unit.base_multiplier)))

        candidates: list[dict] = []
        for lot in lots.values():
            lot_unit = units.get(lot.unit_id)
            if lot.ingredient_id != requirement["ingredient_id"] or lot_unit is None or lot_unit.unit_family != target_unit.unit_family:
                continue
            if requirement["use_date"] and lot.expiration_date and lot.expiration_date < requirement["use_date"]:
                continue
            available_base = capacity.get(lot.id, Decimal("0"))
            if available_base <= 0:
                continue
            payload = _lot_payload(lot, lot_unit, locations.get(lot.location_id), Decimal(lot.quantity))
            payload["available_quantity"] = available_base / Decimal(lot_unit.base_multiplier)
            candidates.append(payload)

        required_base = Decimal(requirement["quantity"]) * Decimal(target_unit.base_multiplier)
        selected_target = selected_base / Decimal(target_unit.base_multiplier)
        output.append({
            **requirement,
            "ingredient_name": ingredient.name,
            "required_quantity": requirement["quantity"],
            "unit_code": target_unit.code,
            "selected_quantity": selected_target,
            "shortage_quantity": max(Decimal("0"), (required_base - selected_base) / Decimal(target_unit.base_multiplier)),
            "selections": selections,
            "suggestions": suggestions,
            "candidates": candidates,
        })
    return {"meal_cycle_id": cycle.id, "meal_cycle_name": cycle.name, "requirements": output}


@router.get("/api/meal-cycles/{cycle_id}/gather", response_model=GatherCycleRead)
def get_gather(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    return _build_cycle(db, _cycle_or_404(db, cycle_id))


@router.post("/api/meal-cycles/{cycle_id}/gather/apply-suggestions", response_model=GatherCycleRead)
def apply_gather_suggestions(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    requirements = _requirements(cycle)
    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    lots = {row.id: row for row in db.scalars(select(InventoryLot).where(InventoryLot.household_id == HOUSEHOLD_ID))}
    planned_ids = [row["planned_meal_id"] for row in requirements]
    if planned_ids:
        db.execute(delete(GatherLotSelection).where(GatherLotSelection.planned_meal_id.in_(planned_ids)))
    for result in allocate_requirement_sequence(db, requirements, exclude_cycle_id=cycle.id):
        target_unit = units[result["unit_id"]]
        for allocation in result["allocations"]:
            lot = lots[allocation["lot_id"]]; lot_unit = units[lot.unit_id]
            base = Decimal(str(allocation["allocated_quantity"])) * Decimal(target_unit.base_multiplier)
            db.add(GatherLotSelection(
                planned_meal_id=result["planned_meal_id"], meal_recipe_id=result["meal_recipe_id"],
                recipe_id=result["recipe_id"], recipe_ingredient_id=result["recipe_ingredient_id"],
                ingredient_id=result["ingredient_id"], lot_id=lot.id,
                quantity=base / Decimal(lot_unit.base_multiplier), unit_id=lot_unit.id,
            ))
    db.commit()
    return _build_cycle(db, cycle)


@router.put("/api/meal-cycles/{cycle_id}/gather/{planned_meal_id}/{meal_recipe_id}/{recipe_ingredient_id}", response_model=GatherCycleRead)
def update_gather_requirement(cycle_id: int, planned_meal_id: int, meal_recipe_id: int, recipe_ingredient_id: int, payload: GatherRequirementUpdate, db: Session = Depends(get_db)) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    requirement = next((row for row in _requirements(cycle) if _key(row) == (planned_meal_id, meal_recipe_id, recipe_ingredient_id)), None)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Gather requirement not found")
    if len({row.lot_id for row in payload.selections}) != len(payload.selections):
        raise HTTPException(status_code=422, detail="A lot may only appear once per Gather requirement")

    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    target_unit = units.get(requirement["unit_id"])
    capacity = _lot_capacity_base(db, cycle, requirement, units)
    required_base = Decimal(requirement["quantity"]) * Decimal(target_unit.base_multiplier)
    selected_base = Decimal("0")
    models: list[GatherLotSelection] = []
    for requested in payload.selections:
        lot = db.get(InventoryLot, requested.lot_id)
        if lot is None or lot.household_id != HOUSEHOLD_ID or lot.ingredient_id != requirement["ingredient_id"]:
            raise HTTPException(status_code=422, detail=f"Lot {requested.lot_id} is not compatible with this ingredient")
        lot_unit = units.get(lot.unit_id)
        if lot_unit is None or lot_unit.unit_family != target_unit.unit_family:
            raise HTTPException(status_code=422, detail=f"Lot {lot.id} has an incompatible unit family")
        if requirement["use_date"] and lot.expiration_date and lot.expiration_date < requirement["use_date"]:
            raise HTTPException(status_code=422, detail=f"Lot {lot.id} expires before the planned use date")
        requested_base = Decimal(requested.quantity) * Decimal(lot_unit.base_multiplier)
        if requested_base - capacity.get(lot.id, Decimal("0")) > TOLERANCE:
            raise HTTPException(status_code=422, detail=f"Lot {lot.id} does not have enough usable quantity")
        selected_base += requested_base
        models.append(GatherLotSelection(
            planned_meal_id=planned_meal_id, meal_recipe_id=meal_recipe_id, recipe_id=requirement["recipe_id"],
            recipe_ingredient_id=recipe_ingredient_id, ingredient_id=requirement["ingredient_id"], lot_id=lot.id,
            quantity=requested.quantity, unit_id=lot_unit.id,
        ))
    if selected_base - required_base > TOLERANCE:
        raise HTTPException(status_code=422, detail="Selected quantity exceeds the Gather requirement")

    db.execute(delete(GatherLotSelection).where(
        GatherLotSelection.planned_meal_id == planned_meal_id,
        GatherLotSelection.meal_recipe_id == meal_recipe_id,
        GatherLotSelection.recipe_ingredient_id == recipe_ingredient_id,
    ))
    db.add_all(models); db.commit()
    return _build_cycle(db, cycle)
