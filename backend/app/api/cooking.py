from __future__ import annotations

import json
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.cooking import PlannedCookingTimer, RecipeCookingTimer
from app.models.ingredient import Ingredient
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.recipe import Recipe, RecipeCookingStep
from app.models.reference import MeasurementUnit
from app.schemas.cooking import CookingStepInput, CookingStepRead, CookingTimerAction, CycleCookingModeResponse

router = APIRouter(tags=["cooking"])
HOUSEHOLD_ID = 1


def _recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.scalar(
        select(Recipe)
        .where(Recipe.id == recipe_id, Recipe.household_id == HOUSEHOLD_ID)
        .options(selectinload(Recipe.cooking_steps), selectinload(Recipe.prep_groups))
    )
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _timer_rows(db: Session, step_ids: list[int]) -> dict[int, list[RecipeCookingTimer]]:
    if not step_ids:
        return {}
    rows = list(db.scalars(
        select(RecipeCookingTimer)
        .where(RecipeCookingTimer.cooking_step_id.in_(step_ids))
        .order_by(RecipeCookingTimer.cooking_step_id, RecipeCookingTimer.sort_order, RecipeCookingTimer.id)
    ))
    result: dict[int, list[RecipeCookingTimer]] = {}
    for row in rows:
        result.setdefault(row.cooking_step_id, []).append(row)
    return result


def _step_payload(step: RecipeCookingStep, group_names: dict[int, str], timers: list[RecipeCookingTimer]) -> dict:
    return {
        "id": step.id,
        "recipe_id": step.recipe_id,
        "prep_group_id": step.prep_group_id,
        "prep_group_name": group_names.get(step.prep_group_id) if step.prep_group_id is not None else None,
        "title": step.title,
        "instructions": step.instructions,
        "sort_order": step.sort_order,
        "timers": [{
            "id": timer.id,
            "cooking_step_id": timer.cooking_step_id,
            "label": timer.label,
            "duration_seconds": timer.duration_seconds,
            "notes": timer.notes,
            "sort_order": timer.sort_order,
        } for timer in timers],
    }


def _runtime_payload(timer: RecipeCookingTimer, runtime: PlannedCookingTimer | None, now: int) -> dict:
    if runtime is None:
        return {
            "timer_id": timer.id,
            "label": timer.label,
            "duration_seconds": timer.duration_seconds,
            "notes": timer.notes,
            "sort_order": timer.sort_order,
            "status": "READY",
            "remaining_seconds": timer.duration_seconds,
            "ends_at_epoch": None,
        }
    if runtime.status == "RUNNING" and runtime.ends_at_epoch is not None:
        remaining = max(runtime.ends_at_epoch - now, 0)
        status = "COMPLETED" if remaining == 0 else "RUNNING"
        if status == "COMPLETED":
            runtime.status = status
            runtime.remaining_seconds = 0
            runtime.ends_at_epoch = None
        return {
            "timer_id": timer.id,
            "label": timer.label,
            "duration_seconds": timer.duration_seconds,
            "notes": timer.notes,
            "sort_order": timer.sort_order,
            "status": status,
            "remaining_seconds": remaining,
            "ends_at_epoch": runtime.ends_at_epoch,
        }
    return {
        "timer_id": timer.id,
        "label": timer.label,
        "duration_seconds": timer.duration_seconds,
        "notes": timer.notes,
        "sort_order": timer.sort_order,
        "status": runtime.status,
        "remaining_seconds": runtime.remaining_seconds,
        "ends_at_epoch": runtime.ends_at_epoch,
    }


@router.get("/api/recipes/{recipe_id}/cooking-steps", response_model=list[CookingStepRead])
def list_cooking_steps(recipe_id: int, db: Session = Depends(get_db)) -> list[dict]:
    recipe = _recipe_or_404(db, recipe_id)
    groups = {group.id: group.name for group in recipe.prep_groups}
    timers = _timer_rows(db, [step.id for step in recipe.cooking_steps])
    return [_step_payload(step, groups, timers.get(step.id, [])) for step in recipe.cooking_steps]


@router.put("/api/recipes/{recipe_id}/cooking-steps", response_model=list[CookingStepRead])
def replace_cooking_steps(recipe_id: int, payload: list[CookingStepInput], db: Session = Depends(get_db)) -> list[dict]:
    recipe = _recipe_or_404(db, recipe_id)
    group_ids = {group.id for group in recipe.prep_groups}
    for item in payload:
        if item.prep_group_id is not None and item.prep_group_id not in group_ids:
            raise HTTPException(status_code=422, detail=f"Prep group {item.prep_group_id} does not belong to this Recipe")

    recipe.cooking_steps.clear()
    db.flush()
    for index, item in enumerate(payload):
        step = RecipeCookingStep(
            prep_group_id=item.prep_group_id,
            title=item.title.strip(),
            instructions=item.instructions.strip() if item.instructions else None,
            sort_order=index,
        )
        recipe.cooking_steps.append(step)
        db.flush()
        for timer_index, timer in enumerate(item.timers):
            db.add(RecipeCookingTimer(
                cooking_step_id=step.id,
                label=timer.label.strip(),
                duration_seconds=timer.duration_seconds,
                notes=timer.notes.strip() if timer.notes else None,
                sort_order=timer_index,
            ))
    db.commit()
    recipe = _recipe_or_404(db, recipe_id)
    groups = {group.id: group.name for group in recipe.prep_groups}
    timers = _timer_rows(db, [step.id for step in recipe.cooking_steps])
    return [_step_payload(step, groups, timers.get(step.id, [])) for step in recipe.cooking_steps]


@router.post("/api/planned-meals/{planned_meal_id}/cooking-timers/{timer_id}")
def update_cooking_timer(planned_meal_id: int, timer_id: int, payload: CookingTimerAction, db: Session = Depends(get_db)) -> dict:
    meal = db.get(PlannedMeal, planned_meal_id)
    timer = db.get(RecipeCookingTimer, timer_id)
    if meal is None or timer is None:
        raise HTTPException(status_code=404, detail="Planned Meal or cooking timer not found")
    step = db.get(RecipeCookingStep, timer.cooking_step_id)
    recipe_ids = {int(item["recipe_id"]) for item in json.loads(meal.scaled_components or "[]") if item.get("recipe_id") is not None}
    if step is None or step.recipe_id not in recipe_ids:
        raise HTTPException(status_code=422, detail="Cooking timer does not belong to this Planned Meal")

    now = int(time.time())
    runtime = db.scalar(select(PlannedCookingTimer).where(
        PlannedCookingTimer.planned_meal_id == planned_meal_id,
        PlannedCookingTimer.cooking_timer_id == timer_id,
    ))
    if runtime is None:
        runtime = PlannedCookingTimer(
            planned_meal_id=planned_meal_id,
            cooking_timer_id=timer_id,
            status="READY",
            remaining_seconds=timer.duration_seconds,
            ends_at_epoch=None,
        )
        db.add(runtime)
        db.flush()

    if runtime.status == "RUNNING" and runtime.ends_at_epoch is not None:
        runtime.remaining_seconds = max(runtime.ends_at_epoch - now, 0)
        if runtime.remaining_seconds == 0:
            runtime.status = "COMPLETED"
            runtime.ends_at_epoch = None

    action = payload.action
    if action == "START":
        runtime.status = "RUNNING"
        runtime.remaining_seconds = timer.duration_seconds
        runtime.ends_at_epoch = now + timer.duration_seconds
    elif action == "RESUME":
        if runtime.status not in {"PAUSED", "COMPLETED"}:
            raise HTTPException(status_code=409, detail="Only paused or completed timers can be resumed")
        if runtime.remaining_seconds <= 0:
            runtime.remaining_seconds = timer.duration_seconds
        runtime.status = "RUNNING"
        runtime.ends_at_epoch = now + runtime.remaining_seconds
    elif action == "PAUSE":
        if runtime.status != "RUNNING":
            raise HTTPException(status_code=409, detail="Only running timers can be paused")
        runtime.status = "PAUSED" if runtime.remaining_seconds > 0 else "COMPLETED"
        runtime.ends_at_epoch = None
    elif action == "RESET":
        runtime.status = "READY"
        runtime.remaining_seconds = timer.duration_seconds
        runtime.ends_at_epoch = None
    elif action == "DISMISS":
        runtime.status = "DISMISSED"
        runtime.remaining_seconds = 0
        runtime.ends_at_epoch = None

    db.commit()
    db.refresh(runtime)
    return _runtime_payload(timer, runtime, int(time.time()))


@router.get("/api/meal-cycles/{cycle_id}/cooking-mode", response_model=CycleCookingModeResponse)
def cycle_cooking_mode(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(
            selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition),
            selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal),
        )
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")

    planned = [slot.planned_meal for slot in cycle.slots if slot.planned_meal is not None]
    recipe_ids: set[int] = set()
    for meal in planned:
        for component in json.loads(meal.scaled_components or "[]"):
            if component.get("recipe_id") is not None:
                recipe_ids.add(int(component["recipe_id"]))

    recipes = list(db.scalars(
        select(Recipe)
        .where(Recipe.id.in_(recipe_ids))
        .options(
            selectinload(Recipe.cooking_steps),
            selectinload(Recipe.prep_groups),
            selectinload(Recipe.ingredients),
        )
    ).unique()) if recipe_ids else []
    recipe_map = {recipe.id: recipe for recipe in recipes}
    all_step_ids = [step.id for recipe in recipes for step in recipe.cooking_steps]
    timers_by_step = _timer_rows(db, all_step_ids)
    all_timer_ids = [timer.id for rows in timers_by_step.values() for timer in rows]
    planned_ids = [meal.id for meal in planned]
    runtimes = list(db.scalars(select(PlannedCookingTimer).where(
        PlannedCookingTimer.planned_meal_id.in_(planned_ids),
        PlannedCookingTimer.cooking_timer_id.in_(all_timer_ids),
    ))) if planned_ids and all_timer_ids else []
    runtime_map = {(row.planned_meal_id, row.cooking_timer_id): row for row in runtimes}

    ingredient_ids: set[int] = set()
    unit_ids: set[int] = set()
    for meal in planned:
        for component in json.loads(meal.scaled_components or "[]"):
            for ingredient in component.get("ingredients", []):
                ingredient_ids.add(int(ingredient["ingredient_id"]))
                unit_ids.add(int(ingredient["unit_id"]))
    ingredient_names = {item.id: item.name for item in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))} if ingredient_ids else {}
    unit_codes = {item.id: item.code for item in db.scalars(select(MeasurementUnit).where(MeasurementUnit.id.in_(unit_ids)))} if unit_ids else {}

    now = int(time.time())
    result_meals: list[dict] = []
    runtime_changed = False
    for slot in cycle.slots:
        meal: PlannedMeal | None = slot.planned_meal
        if meal is None:
            continue
        flat_steps: list[dict] = []
        no_steps: list[str] = []
        components = json.loads(meal.scaled_components or "[]")
        for component_index, component in enumerate(components):
            recipe_id = int(component["recipe_id"])
            recipe = recipe_map.get(recipe_id)
            recipe_name = component.get("recipe_name") or (recipe.name if recipe else f"Recipe {recipe_id}")
            if recipe is None or not recipe.cooking_steps:
                no_steps.append(recipe_name)
                continue
            group_names = {group.id: group.name for group in recipe.prep_groups}
            ingredient_rows = {item.id: item for item in recipe.ingredients}
            component_ingredients: list[dict] = []
            for scaled in component.get("ingredients", []):
                recipe_ingredient = ingredient_rows.get(int(scaled.get("recipe_ingredient_id") or 0))
                component_ingredients.append({"scaled": scaled, "recipe_ingredient": recipe_ingredient})
            for step in recipe.cooking_steps:
                visible = component_ingredients
                if step.prep_group_id is not None:
                    visible = [row for row in component_ingredients if row["recipe_ingredient"] is not None and row["recipe_ingredient"].prep_group_id == step.prep_group_id]
                timer_payloads = []
                for timer in timers_by_step.get(step.id, []):
                    runtime = runtime_map.get((meal.id, timer.id))
                    before = (runtime.status, runtime.remaining_seconds, runtime.ends_at_epoch) if runtime else None
                    item = _runtime_payload(timer, runtime, now)
                    after = (runtime.status, runtime.remaining_seconds, runtime.ends_at_epoch) if runtime else None
                    runtime_changed = runtime_changed or before != after
                    if item["status"] != "DISMISSED":
                        timer_payloads.append(item)
                flat_steps.append({
                    "step_id": step.id,
                    "component_index": component_index,
                    "meal_recipe_id": int(component.get("meal_recipe_id") or -(component_index + 1)),
                    "recipe_id": recipe_id,
                    "recipe_name": recipe_name,
                    "title": step.title,
                    "instructions": step.instructions,
                    "prep_group_id": step.prep_group_id,
                    "prep_group_name": group_names.get(step.prep_group_id) if step.prep_group_id is not None else None,
                    "ingredients": [{
                        "ingredient_id": int(row["scaled"]["ingredient_id"]),
                        "ingredient_name": ingredient_names.get(int(row["scaled"]["ingredient_id"]), f"Ingredient {row['scaled']['ingredient_id']}"),
                        "quantity": Decimal(str(row["scaled"]["quantity"])),
                        "unit_id": int(row["scaled"]["unit_id"]),
                        "unit_code": unit_codes.get(int(row["scaled"]["unit_id"]), str(row["scaled"]["unit_id"])),
                        "preparation": row["recipe_ingredient"].preparation if row["recipe_ingredient"] else None,
                        "prep_method": row["recipe_ingredient"].prep_method if row["recipe_ingredient"] else None,
                        "prep_size": row["recipe_ingredient"].prep_size if row["recipe_ingredient"] else None,
                        "prep_state": row["recipe_ingredient"].prep_state if row["recipe_ingredient"] else None,
                    } for row in visible],
                    "timers": timer_payloads,
                })
        total = len(flat_steps)
        for index, row in enumerate(flat_steps):
            row["step_number"] = index + 1
            row["total_steps"] = total
        result_meals.append({
            "planned_meal_id": meal.id,
            "day_number": slot.day_number,
            "slot_label": slot.slot_definition.label,
            "meal_name": meal.snapshot_name,
            "planned_servings": meal.planned_servings,
            "planned_leftover_servings": meal.planned_leftover_servings,
            "steps": flat_steps,
            "components_without_steps": no_steps,
        })
    if runtime_changed:
        db.commit()
    return {"cycle_id": cycle_id, "meals": result_meals}
