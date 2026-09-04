from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.completion import MealCompletion, MealCompletionUsage
from app.models.ingredient import Ingredient
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.recipe import Recipe, RecipeIngredientSubstitution
from app.models.reference import MeasurementUnit
from app.schemas.completion import CompletionDraftUpdate, MealCompletionRead
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/planned-meals", tags=["meal-completion"])
HOUSEHOLD_ID = 1


def _planned_or_404(db: Session, planned_meal_id: int) -> PlannedMeal:
    planned = db.scalar(
        select(PlannedMeal)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .join(MealCycle, MealCycle.id == CycleSlot.cycle_id)
        .where(PlannedMeal.id == planned_meal_id, MealCycle.household_id == HOUSEHOLD_ID)
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
        .options(selectinload(MealCompletion.usages))
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
    return {
        "id": completion.id,
        "planned_meal_id": planned.id,
        "status": completion.status,
        "meal_name": completion.snapshot_name,
        "snapshot_planned_servings": completion.snapshot_planned_servings,
        "snapshot_planned_leftover_servings": completion.snapshot_planned_leftover_servings,
        "stale": completion.plan_fingerprint != _fingerprint(planned),
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
        } for row in completion.usages],
    }


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
