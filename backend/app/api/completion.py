from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.completion import MealCompletion, MealCompletionAllocation, MealCompletionUsage
from app.models.gather import GatherLotSelection
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.recipe import Recipe, RecipeIngredientSubstitution
from app.models.reference import MeasurementUnit
from app.schemas.completion import CompletionDraftUpdate, CompletionFinalizeResponse, MealCompletionRead
from app.services.inventory_allocation import _consume_other_reservations, _load_states, _lot_sort_key
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/planned-meals", tags=["meal-completion"])
HOUSEHOLD_ID = 1
TOLERANCE = Decimal("0.000001")


def _planned_or_404(db: Session, planned_meal_id: int) -> PlannedMeal:
    planned = db.scalar(
        select(PlannedMeal)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .join(MealCycle, MealCycle.id == CycleSlot.cycle_id)
        .where(PlannedMeal.id == planned_meal_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(PlannedMeal.cycle_slot).selectinload(CycleSlot.cycle))
    )
    if planned is None:
        raise HTTPException(status_code=404, detail="Planned Meal not found")
    return planned


def _fingerprint(planned: PlannedMeal) -> str:
    payload = {
        "planned_servings": str(planned.planned_servings),
        "planned_leftover_servings": str(planned.planned_leftover_servings),
        "component_serving_overrides": json.loads(planned.component_serving_overrides or "{}"),
        "scaled_components": json.loads(planned.scaled_components or "[]"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_completion(db: Session, planned_meal_id: int) -> MealCompletion | None:
    return db.scalar(
        select(MealCompletion)
        .where(MealCompletion.planned_meal_id == planned_meal_id)
        .options(selectinload(MealCompletion.usages), selectinload(MealCompletion.allocations))
        .execution_options(populate_existing=True)
    )


def _source_rows(db: Session, planned: PlannedMeal) -> list[dict]:
    components = json.loads(planned.scaled_components or "[]")
    recipe_ids = {int(row["recipe_id"]) for row in components}
    recipes = list(db.scalars(
        select(Recipe).where(Recipe.id.in_(recipe_ids)).options(selectinload(Recipe.ingredients))
    ).unique()) if recipe_ids else []
    recipe_map = {recipe.id: recipe for recipe in recipes}
    ingredient_ids = {int(item["ingredient_id"]) for component in components for item in component.get("ingredients", [])}
    unit_ids = {int(item["unit_id"]) for component in components for item in component.get("ingredients", [])}
    ingredient_names = {row.id: row.name for row in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))} if ingredient_ids else {}
    unit_codes = {row.id: row.code for row in db.scalars(select(MeasurementUnit).where(MeasurementUnit.id.in_(unit_ids)))} if unit_ids else {}

    result: list[dict] = []
    for index, component in enumerate(components):
        recipe_id = int(component["recipe_id"])
        recipe = recipe_map.get(recipe_id)
        component_key = int(component.get("meal_recipe_id") or -(index + 1))
        recipe_name = component.get("recipe_name") or (recipe.name if recipe else f"Recipe {recipe_id}")
        recipe_ingredients = {row.id: row for row in recipe.ingredients} if recipe else {}
        for scaled in component.get("ingredients", []):
            recipe_ingredient_id = int(scaled["recipe_ingredient_id"])
            recipe_ingredient = recipe_ingredients.get(recipe_ingredient_id)
            ingredient_id = int(scaled["ingredient_id"])
            unit_id = int(scaled["unit_id"])
            result.append({
                "component_key": component_key,
                "recipe_id": recipe_id,
                "recipe_name": recipe_name,
                "recipe_ingredient_id": recipe_ingredient_id,
                "planned_ingredient_id": ingredient_id,
                "planned_ingredient_name": ingredient_names.get(ingredient_id, f"Ingredient {ingredient_id}"),
                "planned_quantity": Decimal(str(scaled["quantity"])),
                "planned_unit_id": unit_id,
                "planned_unit_code": unit_codes.get(unit_id, str(unit_id)),
                "preparation": recipe_ingredient.preparation if recipe_ingredient else None,
                "prep_method": recipe_ingredient.prep_method if recipe_ingredient else None,
                "prep_size": recipe_ingredient.prep_size if recipe_ingredient else None,
                "prep_state": recipe_ingredient.prep_state if recipe_ingredient else None,
            })
    return result


def _create_draft(db: Session, planned: PlannedMeal) -> MealCompletion:
    completion = MealCompletion(
        planned_meal_id=planned.id,
        status="DRAFT",
        plan_fingerprint=_fingerprint(planned),
        snapshot_name=planned.snapshot_name,
        snapshot_planned_servings=planned.planned_servings,
        snapshot_planned_leftover_servings=planned.planned_leftover_servings,
        snapshot_scaled_components=planned.scaled_components,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(completion)
    db.flush()
    for row in _source_rows(db, planned):
        db.add(MealCompletionUsage(
            completion_id=completion.id,
            **row,
            actual_ingredient_id=row["planned_ingredient_id"],
            actual_ingredient_name=row["planned_ingredient_name"],
            actual_quantity=row["planned_quantity"],
            actual_unit_id=row["planned_unit_id"],
            actual_unit_code=row["planned_unit_code"],
            notes=None,
        ))
    db.commit()
    return _load_completion(db, planned.id)  # type: ignore[return-value]


def _substitution_map(db: Session, recipe_ingredient_ids: list[int]) -> dict[int, list[dict]]:
    if not recipe_ingredient_ids:
        return {}
    rows = list(db.scalars(
        select(RecipeIngredientSubstitution)
        .where(RecipeIngredientSubstitution.recipe_ingredient_id.in_(recipe_ingredient_ids))
        .order_by(RecipeIngredientSubstitution.recipe_ingredient_id, RecipeIngredientSubstitution.preferred.desc(), RecipeIngredientSubstitution.sort_order)
    ))
    ingredient_ids = {row.substitute_ingredient_id for row in rows}
    names = {row.id: row.name for row in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))} if ingredient_ids else {}
    result: dict[int, list[dict]] = {}
    for row in rows:
        result.setdefault(row.recipe_ingredient_id, []).append({
            "ingredient_id": row.substitute_ingredient_id,
            "ingredient_name": names.get(row.substitute_ingredient_id, f"Ingredient {row.substitute_ingredient_id}"),
            "ratio": row.ratio,
            "preferred": row.preferred,
            "notes": row.notes,
        })
    return result


def _payload(db: Session, planned: PlannedMeal, completion: MealCompletion) -> dict:
    substitutions = _substitution_map(db, [row.recipe_ingredient_id for row in completion.usages])
    allocations_by_usage: dict[int, list[MealCompletionAllocation]] = {}
    for allocation in completion.allocations:
        allocations_by_usage.setdefault(allocation.usage_id, []).append(allocation)
    return {
        "id": completion.id,
        "planned_meal_id": planned.id,
        "status": completion.status,
        "meal_name": completion.snapshot_name,
        "snapshot_planned_servings": completion.snapshot_planned_servings,
        "snapshot_planned_leftover_servings": completion.snapshot_planned_leftover_servings,
        "stale": completion.plan_fingerprint != _fingerprint(planned),
        "finalized_at": completion.finalized_at,
        "usages": [{
            "id": row.id,
            "component_key": row.component_key,
            "recipe_id": row.recipe_id,
            "recipe_name": row.recipe_name,
            "recipe_ingredient_id": row.recipe_ingredient_id,
            "planned_ingredient_id": row.planned_ingredient_id,
            "planned_ingredient_name": row.planned_ingredient_name,
            "planned_quantity": row.planned_quantity,
            "planned_unit_id": row.planned_unit_id,
            "planned_unit_code": row.planned_unit_code,
            "actual_ingredient_id": row.actual_ingredient_id,
            "actual_ingredient_name": row.actual_ingredient_name,
            "actual_quantity": row.actual_quantity,
            "actual_unit_id": row.actual_unit_id,
            "actual_unit_code": row.actual_unit_code,
            "preparation": row.preparation,
            "prep_method": row.prep_method,
            "prep_size": row.prep_size,
            "prep_state": row.prep_state,
            "notes": row.notes,
            "substitutions": substitutions.get(row.recipe_ingredient_id, []),
            "allocations": [{
                "id": allocation.id,
                "usage_id": allocation.usage_id,
                "lot_id": allocation.lot_id,
                "inventory_transaction_id": allocation.inventory_transaction_id,
                "quantity": allocation.quantity,
                "unit_id": allocation.unit_id,
                "unit_code": allocation.unit_code,
                "source_quantity": allocation.source_quantity,
                "source_unit_id": allocation.source_unit_id,
                "source_unit_code": allocation.source_unit_code,
            } for allocation in allocations_by_usage.get(row.id, [])],
        } for row in completion.usages],
    }


def _finalization_plan(db: Session, planned: PlannedMeal, completion: MealCompletion) -> tuple[list[dict], list[dict]]:
    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    ingredients = {row.id: row for row in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))}
    gathers = list(db.scalars(select(GatherLotSelection).where(GatherLotSelection.planned_meal_id == planned.id)))
    gather_by_key: dict[tuple[int, int], list[GatherLotSelection]] = {}
    for row in gathers:
        gather_by_key.setdefault((row.meal_recipe_id, row.recipe_ingredient_id), []).append(row)

    state_cache: dict[tuple[int, str], list] = {}
    reservation_consumed: set[tuple[int, str]] = set()
    allocations: list[dict] = []
    shortages: list[dict] = []
    cycle_id = planned.cycle_slot.cycle_id
    use_date = planned.scheduled_date

    for usage in completion.usages:
        if Decimal(usage.actual_quantity) <= 0:
            continue
        target_unit = units.get(usage.actual_unit_id)
        ingredient = ingredients.get(usage.actual_ingredient_id)
        if target_unit is None or ingredient is None:
            shortages.append({
                "usage_id": usage.id, "ingredient_id": usage.actual_ingredient_id,
                "ingredient_name": usage.actual_ingredient_name, "requested_quantity": usage.actual_quantity,
                "unit_id": usage.actual_unit_id, "unit_code": usage.actual_unit_code,
                "shortage_quantity": usage.actual_quantity,
            })
            continue
        key = (ingredient.id, target_unit.unit_family)
        states = state_cache.setdefault(key, _load_states(db, ingredient.id, target_unit.unit_family, units))
        if key not in reservation_consumed:
            _consume_other_reservations(
                db, states, ingredient.id, target_unit.unit_family, units,
                ingredient.default_location_id, use_date, cycle_id,
            )
            reservation_consumed.add(key)

        state_by_lot = {state.lot.id: state for state in states}
        required_base = Decimal(usage.actual_quantity) * Decimal(target_unit.base_multiplier)
        remaining_base = required_base
        usage_allocations: list[dict] = []

        for selected in sorted(gather_by_key.get((usage.component_key, usage.recipe_ingredient_id), []), key=lambda row: row.id):
            if remaining_base <= TOLERANCE or selected.ingredient_id != usage.actual_ingredient_id:
                continue
            state = state_by_lot.get(selected.lot_id)
            selected_unit = units.get(selected.unit_id)
            if state is None or selected_unit is None or selected_unit.unit_family != target_unit.unit_family:
                continue
            selected_base = Decimal(selected.quantity) * Decimal(selected_unit.base_multiplier)
            consumed_base = min(remaining_base, state.remaining_base, selected_base)
            if consumed_base <= TOLERANCE:
                continue
            state.remaining_base -= consumed_base
            remaining_base -= consumed_base
            usage_allocations.append({
                "usage": usage,
                "lot": state.lot,
                "target_unit": target_unit,
                "lot_unit": state.unit,
                "target_quantity": consumed_base / Decimal(target_unit.base_multiplier),
                "source_quantity": consumed_base / Decimal(state.unit.base_multiplier),
            })

        eligible = [
            state for state in states
            if state.remaining_base > TOLERANCE
            and (use_date is None or state.lot.expiration_date is None or state.lot.expiration_date >= use_date)
        ]
        for state in sorted(eligible, key=lambda row: _lot_sort_key(row, ingredient.default_location_id)):
            if remaining_base <= TOLERANCE:
                break
            consumed_base = min(remaining_base, state.remaining_base)
            state.remaining_base -= consumed_base
            remaining_base -= consumed_base
            usage_allocations.append({
                "usage": usage,
                "lot": state.lot,
                "target_unit": target_unit,
                "lot_unit": state.unit,
                "target_quantity": consumed_base / Decimal(target_unit.base_multiplier),
                "source_quantity": consumed_base / Decimal(state.unit.base_multiplier),
            })

        if remaining_base > TOLERANCE:
            shortages.append({
                "usage_id": usage.id, "ingredient_id": ingredient.id,
                "ingredient_name": usage.actual_ingredient_name, "requested_quantity": usage.actual_quantity,
                "unit_id": target_unit.id, "unit_code": target_unit.code,
                "shortage_quantity": remaining_base / Decimal(target_unit.base_multiplier),
            })
        allocations.extend(usage_allocations)

    return allocations, shortages


@router.post("/{planned_meal_id}/completion", response_model=MealCompletionRead)
def start_completion(planned_meal_id: int, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id) or _create_draft(db, planned)
    return _payload(db, planned, completion)


@router.get("/{planned_meal_id}/completion", response_model=MealCompletionRead)
def get_completion(planned_meal_id: int, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None:
        raise HTTPException(status_code=404, detail="Meal completion draft not started")
    return _payload(db, planned, completion)


@router.put("/{planned_meal_id}/completion", response_model=MealCompletionRead)
def update_completion(planned_meal_id: int, payload: CompletionDraftUpdate, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None:
        raise HTTPException(status_code=404, detail="Meal completion draft not started")
    if completion.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Finalized completion cannot be edited")

    rows = {row.id: row for row in completion.usages}
    if {item.usage_id for item in payload.usages} != set(rows):
        raise HTTPException(status_code=422, detail="Completion update must include every usage row exactly once")
    if len(payload.usages) != len({item.usage_id for item in payload.usages}):
        raise HTTPException(status_code=422, detail="Duplicate completion usage row")

    ingredient_ids = {item.actual_ingredient_id for item in payload.usages}
    unit_ids = {item.actual_unit_id for item in payload.usages} | {row.planned_unit_id for row in completion.usages}
    ingredients = {row.id: row for row in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids), Ingredient.household_id == HOUSEHOLD_ID))}
    units = {row.id: row for row in db.scalars(select(MeasurementUnit).where(MeasurementUnit.id.in_(unit_ids)))}
    if len(ingredients) != len(ingredient_ids):
        raise HTTPException(status_code=422, detail="Actual Ingredient must belong to this household")

    for item in payload.usages:
        row = rows[item.usage_id]
        ingredient = ingredients[item.actual_ingredient_id]
        if not ingredient.active and ingredient.id != row.actual_ingredient_id:
            raise HTTPException(status_code=422, detail="Archived Ingredients cannot be selected for new actual usage")
        actual_unit = units.get(item.actual_unit_id)
        planned_unit = units.get(row.planned_unit_id)
        if actual_unit is None or planned_unit is None:
            raise HTTPException(status_code=422, detail="Unknown measurement unit")
        try:
            convert_quantity(item.actual_quantity, actual_unit, planned_unit)
        except UnitConversionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.actual_ingredient_id = ingredient.id
        row.actual_ingredient_name = ingredient.name
        row.actual_quantity = item.actual_quantity
        row.actual_unit_id = actual_unit.id
        row.actual_unit_code = actual_unit.code
        row.notes = item.notes.strip() if item.notes else None
    completion.updated_at = datetime.utcnow()
    db.commit()
    completion = _load_completion(db, planned_meal_id)  # type: ignore[assignment]
    return _payload(db, planned, completion)


@router.post("/{planned_meal_id}/completion/refresh", response_model=MealCompletionRead)
def refresh_completion(planned_meal_id: int, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None:
        raise HTTPException(status_code=404, detail="Meal completion draft not started")
    if completion.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Finalized completion cannot be refreshed")

    existing = {(row.component_key, row.recipe_ingredient_id): row for row in completion.usages}
    new_sources = _source_rows(db, planned)
    completion.usages.clear()
    db.flush()
    for source in new_sources:
        previous = existing.get((source["component_key"], source["recipe_ingredient_id"]))
        db.add(MealCompletionUsage(
            completion_id=completion.id,
            **source,
            actual_ingredient_id=previous.actual_ingredient_id if previous else source["planned_ingredient_id"],
            actual_ingredient_name=previous.actual_ingredient_name if previous else source["planned_ingredient_name"],
            actual_quantity=previous.actual_quantity if previous else source["planned_quantity"],
            actual_unit_id=previous.actual_unit_id if previous else source["planned_unit_id"],
            actual_unit_code=previous.actual_unit_code if previous else source["planned_unit_code"],
            notes=previous.notes if previous else None,
        ))
    completion.plan_fingerprint = _fingerprint(planned)
    completion.snapshot_name = planned.snapshot_name
    completion.snapshot_planned_servings = planned.planned_servings
    completion.snapshot_planned_leftover_servings = planned.planned_leftover_servings
    completion.snapshot_scaled_components = planned.scaled_components
    completion.updated_at = datetime.utcnow()
    db.commit()
    completion = _load_completion(db, planned_meal_id)  # type: ignore[assignment]
    return _payload(db, planned, completion)


@router.post("/{planned_meal_id}/completion/finalize", response_model=CompletionFinalizeResponse)
def finalize_completion(planned_meal_id: int, db: Session = Depends(get_db)) -> dict:
    planned = _planned_or_404(db, planned_meal_id)
    completion = _load_completion(db, planned_meal_id)
    if completion is None:
        raise HTTPException(status_code=404, detail="Meal completion draft not started")
    if completion.status == "FINALIZED":
        return {"completion": _payload(db, planned, completion), "shortages": []}
    if completion.plan_fingerprint != _fingerprint(planned):
        raise HTTPException(status_code=409, detail="Completion draft is stale; refresh it before finalizing")

    allocation_plan, shortages = _finalization_plan(db, planned, completion)
    if shortages:
        db.rollback()
        raise HTTPException(status_code=409, detail={"message": "Insufficient Inventory to finalize Meal completion", "shortages": shortages})

    try:
        for item in allocation_plan:
            lot: InventoryLot = item["lot"]
            source_quantity = Decimal(item["source_quantity"])
            current = Decimal(lot.quantity)
            if source_quantity - current > TOLERANCE:
                raise HTTPException(status_code=409, detail="Inventory changed while finalizing; retry after reviewing the draft")
            lot.quantity = current - source_quantity
            transaction = InventoryTransaction(
                household_id=HOUSEHOLD_ID,
                lot_id=lot.id,
                transaction_type="CONSUME",
                quantity_delta=-source_quantity,
                unit_id=lot.unit_id,
                note=f"Meal completion #{completion.id} / PlannedMeal #{planned.id} / usage #{item['usage'].id}",
            )
            db.add(transaction)
            db.flush()
            db.add(MealCompletionAllocation(
                completion_id=completion.id,
                usage_id=item["usage"].id,
                lot_id=lot.id,
                inventory_transaction_id=transaction.id,
                quantity=item["target_quantity"],
                unit_id=item["target_unit"].id,
                unit_code=item["target_unit"].code,
                source_quantity=source_quantity,
                source_unit_id=item["lot_unit"].id,
                source_unit_code=item["lot_unit"].code,
            ))
        now = datetime.utcnow()
        completion.status = "FINALIZED"
        completion.finalized_at = now
        completion.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise

    completion = _load_completion(db, planned_meal_id)  # type: ignore[assignment]
    return {"completion": _payload(db, planned, completion), "shortages": []}
