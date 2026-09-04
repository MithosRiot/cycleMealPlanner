from __future__ import annotations

import json
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.cooking import (
    PlannedCookingTimer,
    RecipeCookingCoordination,
    RecipeCookingDependency,
    RecipeCookingStepEquipment,
    RecipeCookingTemperature,
    RecipeCookingTimer,
)
from app.models.equipment import Equipment
from app.models.ingredient import Ingredient
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.recipe import Recipe, RecipeCookingStep, RecipeEquipment
from app.models.reference import MeasurementUnit
from app.schemas.cooking import CookingStepInput, CookingStepRead, CookingTimerAction, CycleCookingModeResponse

router = APIRouter(tags=["cooking"])
HOUSEHOLD_ID = 1


def _recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.scalar(
        select(Recipe)
        .where(Recipe.id == recipe_id, Recipe.household_id == HOUSEHOLD_ID)
        .options(selectinload(Recipe.cooking_steps), selectinload(Recipe.prep_groups), selectinload(Recipe.equipment))
    )
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _timer_rows(db: Session, step_ids: list[int]) -> dict[int, list[RecipeCookingTimer]]:
    if not step_ids:
        return {}
    rows = list(db.scalars(select(RecipeCookingTimer).where(RecipeCookingTimer.cooking_step_id.in_(step_ids)).order_by(RecipeCookingTimer.cooking_step_id, RecipeCookingTimer.sort_order, RecipeCookingTimer.id)))
    result: dict[int, list[RecipeCookingTimer]] = {}
    for row in rows:
        result.setdefault(row.cooking_step_id, []).append(row)
    return result


def _temperature_rows(db: Session, step_ids: list[int]) -> dict[int, list[RecipeCookingTemperature]]:
    if not step_ids:
        return {}
    rows = list(db.scalars(select(RecipeCookingTemperature).where(RecipeCookingTemperature.cooking_step_id.in_(step_ids)).order_by(RecipeCookingTemperature.cooking_step_id, RecipeCookingTemperature.sort_order, RecipeCookingTemperature.id)))
    result: dict[int, list[RecipeCookingTemperature]] = {}
    for row in rows:
        result.setdefault(row.cooking_step_id, []).append(row)
    return result


def _equipment_rows(db: Session, step_ids: list[int]) -> dict[int, list[dict]]:
    if not step_ids:
        return {}
    links = list(db.scalars(select(RecipeCookingStepEquipment).where(RecipeCookingStepEquipment.cooking_step_id.in_(step_ids)).order_by(RecipeCookingStepEquipment.cooking_step_id, RecipeCookingStepEquipment.sort_order, RecipeCookingStepEquipment.id)))
    recipe_equipment_ids = {row.recipe_equipment_id for row in links}
    requirements = {row.id: row for row in db.scalars(select(RecipeEquipment).where(RecipeEquipment.id.in_(recipe_equipment_ids)))} if recipe_equipment_ids else {}
    equipment_ids = {row.equipment_id for row in requirements.values()}
    names = {row.id: row.name for row in db.scalars(select(Equipment).where(Equipment.id.in_(equipment_ids)))} if equipment_ids else {}
    result: dict[int, list[dict]] = {}
    for link in links:
        requirement = requirements.get(link.recipe_equipment_id)
        if requirement is None:
            continue
        result.setdefault(link.cooking_step_id, []).append({
            "recipe_equipment_id": requirement.id,
            "equipment_id": requirement.equipment_id,
            "equipment_name": names.get(requirement.equipment_id, f"Equipment {requirement.equipment_id}"),
            "quantity": requirement.quantity,
            "notes": requirement.notes,
            "sort_order": link.sort_order,
        })
    return result


def _coordination_rows(db: Session, step_ids: list[int]) -> dict[int, RecipeCookingCoordination]:
    if not step_ids:
        return {}
    return {row.cooking_step_id: row for row in db.scalars(select(RecipeCookingCoordination).where(RecipeCookingCoordination.cooking_step_id.in_(step_ids)))}


def _dependency_rows(db: Session, step_ids: list[int]) -> dict[int, list[int]]:
    if not step_ids:
        return {}
    rows = list(db.scalars(select(RecipeCookingDependency).where(RecipeCookingDependency.cooking_step_id.in_(step_ids))))
    result: dict[int, list[int]] = {}
    for row in rows:
        result.setdefault(row.cooking_step_id, []).append(row.depends_on_step_id)
    return result


def _temperature_payload(row: RecipeCookingTemperature) -> dict:
    return {"id": row.id, "cooking_step_id": row.cooking_step_id, "label": row.label, "value": row.value, "unit": row.unit, "notes": row.notes, "sort_order": row.sort_order}


def _step_payload(step: RecipeCookingStep, group_names: dict[int, str], timers: list[RecipeCookingTimer], equipment: list[dict], temperatures: list[RecipeCookingTemperature], coordination: RecipeCookingCoordination | None, dependency_ids: list[int], order_by_id: dict[int, int]) -> dict:
    return {
        "id": step.id,
        "recipe_id": step.recipe_id,
        "prep_group_id": step.prep_group_id,
        "prep_group_name": group_names.get(step.prep_group_id) if step.prep_group_id is not None else None,
        "title": step.title,
        "instructions": step.instructions,
        "sort_order": step.sort_order,
        "timers": [{"id": timer.id, "cooking_step_id": timer.cooking_step_id, "label": timer.label, "duration_seconds": timer.duration_seconds, "notes": timer.notes, "sort_order": timer.sort_order} for timer in timers],
        "equipment": equipment,
        "temperatures": [_temperature_payload(row) for row in temperatures],
        "coordination_stage": coordination.stage if coordination else 0,
        "parallel_capable": bool(coordination.parallel_capable) if coordination else False,
        "depends_on_step_orders": sorted(order_by_id[item] for item in dependency_ids if item in order_by_id),
    }


def _runtime_payload(timer: RecipeCookingTimer, runtime: PlannedCookingTimer | None, now: int) -> dict:
    if runtime is None:
        return {"timer_id": timer.id, "label": timer.label, "duration_seconds": timer.duration_seconds, "notes": timer.notes, "sort_order": timer.sort_order, "status": "READY", "remaining_seconds": timer.duration_seconds, "ends_at_epoch": None}
    if runtime.status == "RUNNING" and runtime.ends_at_epoch is not None:
        remaining = max(runtime.ends_at_epoch - now, 0)
        status = "COMPLETED" if remaining == 0 else "RUNNING"
        if status == "COMPLETED":
            runtime.status = status
            runtime.remaining_seconds = 0
            runtime.ends_at_epoch = None
        return {"timer_id": timer.id, "label": timer.label, "duration_seconds": timer.duration_seconds, "notes": timer.notes, "sort_order": timer.sort_order, "status": status, "remaining_seconds": remaining, "ends_at_epoch": runtime.ends_at_epoch}
    return {"timer_id": timer.id, "label": timer.label, "duration_seconds": timer.duration_seconds, "notes": timer.notes, "sort_order": timer.sort_order, "status": runtime.status, "remaining_seconds": runtime.remaining_seconds, "ends_at_epoch": runtime.ends_at_epoch}


def _validate_coordination(payload: list[CookingStepInput]) -> None:
    count = len(payload)
    graph: dict[int, set[int]] = {}
    for index, item in enumerate(payload):
        dependencies = set(item.depends_on_step_orders)
        if len(dependencies) != len(item.depends_on_step_orders):
            raise HTTPException(status_code=422, detail=f"Cooking step {index + 1} has duplicate dependencies")
        if any(value < 0 or value >= count for value in dependencies):
            raise HTTPException(status_code=422, detail=f"Cooking step {index + 1} references a missing dependency")
        if index in dependencies:
            raise HTTPException(status_code=422, detail=f"Cooking step {index + 1} cannot depend on itself")
        if index > 0:
            dependencies.add(index - 1)
        graph[index] = dependencies

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(node: int) -> None:
        if node in visiting:
            raise HTTPException(status_code=422, detail="Cooking step coordination contains a dependency cycle")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


@router.get("/api/recipes/{recipe_id}/cooking-steps", response_model=list[CookingStepRead])
def list_cooking_steps(recipe_id: int, db: Session = Depends(get_db)) -> list[dict]:
    recipe = _recipe_or_404(db, recipe_id)
    groups = {group.id: group.name for group in recipe.prep_groups}
    step_ids = [step.id for step in recipe.cooking_steps]
    timers = _timer_rows(db, step_ids)
    equipment = _equipment_rows(db, step_ids)
    temperatures = _temperature_rows(db, step_ids)
    coordination = _coordination_rows(db, step_ids)
    dependencies = _dependency_rows(db, step_ids)
    order_by_id = {step.id: step.sort_order for step in recipe.cooking_steps}
    return [_step_payload(step, groups, timers.get(step.id, []), equipment.get(step.id, []), temperatures.get(step.id, []), coordination.get(step.id), dependencies.get(step.id, []), order_by_id) for step in recipe.cooking_steps]


@router.put("/api/recipes/{recipe_id}/cooking-steps", response_model=list[CookingStepRead])
def replace_cooking_steps(recipe_id: int, payload: list[CookingStepInput], db: Session = Depends(get_db)) -> list[dict]:
    recipe = _recipe_or_404(db, recipe_id)
    group_ids = {group.id for group in recipe.prep_groups}
    recipe_equipment_ids = {row.id for row in recipe.equipment}
    _validate_coordination(payload)
    for item in payload:
        if item.prep_group_id is not None and item.prep_group_id not in group_ids:
            raise HTTPException(status_code=422, detail=f"Prep group {item.prep_group_id} does not belong to this Recipe")
        invalid_equipment = [row_id for row_id in item.recipe_equipment_ids if row_id not in recipe_equipment_ids]
        if invalid_equipment:
            raise HTTPException(status_code=422, detail=f"Recipe equipment {invalid_equipment[0]} does not belong to this Recipe")
        if len(set(item.recipe_equipment_ids)) != len(item.recipe_equipment_ids):
            raise HTTPException(status_code=422, detail="Cooking step equipment references must be unique")

    recipe.cooking_steps.clear()
    db.flush()
    new_steps: list[RecipeCookingStep] = []
    for index, item in enumerate(payload):
        step = RecipeCookingStep(prep_group_id=item.prep_group_id, title=item.title.strip(), instructions=item.instructions.strip() if item.instructions else None, sort_order=index)
        recipe.cooking_steps.append(step)
        db.flush()
        new_steps.append(step)
        for timer_index, timer in enumerate(item.timers):
            db.add(RecipeCookingTimer(cooking_step_id=step.id, label=timer.label.strip(), duration_seconds=timer.duration_seconds, notes=timer.notes.strip() if timer.notes else None, sort_order=timer_index))
        for equipment_index, recipe_equipment_id in enumerate(item.recipe_equipment_ids):
            db.add(RecipeCookingStepEquipment(cooking_step_id=step.id, recipe_equipment_id=recipe_equipment_id, sort_order=equipment_index))
        for temperature_index, temperature in enumerate(item.temperatures):
            db.add(RecipeCookingTemperature(cooking_step_id=step.id, label=temperature.label.strip(), value=temperature.value, unit=temperature.unit, notes=temperature.notes.strip() if temperature.notes else None, sort_order=temperature_index))
        if item.coordination_stage != 0 or item.parallel_capable or item.depends_on_step_orders:
            db.add(RecipeCookingCoordination(cooking_step_id=step.id, stage=item.coordination_stage, parallel_capable=item.parallel_capable))
    db.flush()
    for index, item in enumerate(payload):
        for dependency_order in item.depends_on_step_orders:
            db.add(RecipeCookingDependency(cooking_step_id=new_steps[index].id, depends_on_step_id=new_steps[dependency_order].id))
    db.commit()
    return list_cooking_steps(recipe_id, db)


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
    runtime = db.scalar(select(PlannedCookingTimer).where(PlannedCookingTimer.planned_meal_id == planned_meal_id, PlannedCookingTimer.cooking_timer_id == timer_id))
    if runtime is None:
        runtime = PlannedCookingTimer(planned_meal_id=planned_meal_id, cooking_timer_id=timer_id, status="READY", remaining_seconds=timer.duration_seconds, ends_at_epoch=None)
        db.add(runtime)
        db.flush()
    if runtime.status == "RUNNING" and runtime.ends_at_epoch is not None:
        runtime.remaining_seconds = max(runtime.ends_at_epoch - now, 0)
        if runtime.remaining_seconds == 0:
            runtime.status = "COMPLETED"
            runtime.ends_at_epoch = None
    action = payload.action
    if action == "START":
        runtime.status = "RUNNING"; runtime.remaining_seconds = timer.duration_seconds; runtime.ends_at_epoch = now + timer.duration_seconds
    elif action == "RESUME":
        if runtime.status not in {"PAUSED", "COMPLETED"}:
            raise HTTPException(status_code=409, detail="Only paused or completed timers can be resumed")
        if runtime.remaining_seconds <= 0:
            runtime.remaining_seconds = timer.duration_seconds
        runtime.status = "RUNNING"; runtime.ends_at_epoch = now + runtime.remaining_seconds
    elif action == "PAUSE":
        if runtime.status != "RUNNING":
            raise HTTPException(status_code=409, detail="Only running timers can be paused")
        runtime.status = "PAUSED" if runtime.remaining_seconds > 0 else "COMPLETED"; runtime.ends_at_epoch = None
    elif action == "RESET":
        runtime.status = "READY"; runtime.remaining_seconds = timer.duration_seconds; runtime.ends_at_epoch = None
    elif action == "DISMISS":
        runtime.status = "DISMISSED"; runtime.remaining_seconds = 0; runtime.ends_at_epoch = None
    db.commit(); db.refresh(runtime)
    return _runtime_payload(timer, runtime, int(time.time()))


def _coordinate_steps(nodes: list[dict], explicit_dependencies: dict[int, list[int]], coordination: dict[int, RecipeCookingCoordination]) -> list[dict]:
    if not nodes:
        return nodes
    relevant_ids = {node["step_id"] for node in nodes}
    coordinated = any(step_id in coordination or explicit_dependencies.get(step_id) for step_id in relevant_ids)
    if not coordinated:
        for node in nodes:
            node["parallel_group"] = None
        return nodes

    by_component: dict[int, list[dict]] = {}
    for node in nodes:
        by_component.setdefault(node["component_index"], []).append(node)
    dependency_keys: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for component_index, component_nodes in by_component.items():
        step_ids_in_component = {node["step_id"] for node in component_nodes}
        for index, node in enumerate(component_nodes):
            key = (component_index, node["step_id"])
            deps: set[tuple[int, int]] = set()
            if index > 0:
                deps.add((component_index, component_nodes[index - 1]["step_id"]))
            for dependency_id in explicit_dependencies.get(node["step_id"], []):
                if dependency_id in step_ids_in_component:
                    deps.add((component_index, dependency_id))
            dependency_keys[key] = deps

    pending = {(node["component_index"], node["step_id"]): node for node in nodes}
    completed: set[tuple[int, int]] = set()
    ordered: list[dict] = []
    parallel_group = 1
    while pending:
        ready = [(key, node) for key, node in pending.items() if dependency_keys[key].issubset(completed)]
        if not ready:
            raise HTTPException(status_code=409, detail="Cooking coordination contains a dependency cycle")
        minimum_stage = min(node["coordination_stage"] for _key, node in ready)
        batch = [(key, node) for key, node in ready if node["coordination_stage"] == minimum_stage]
        batch.sort(key=lambda item: (item[1]["component_index"], item[1]["source_sort_order"], item[1]["step_id"]))
        group_value = parallel_group if len(batch) > 1 and all(node["parallel_capable"] for _key, node in batch) else None
        if group_value is not None:
            parallel_group += 1
        for key, node in batch:
            node["parallel_group"] = group_value
            ordered.append(node)
            completed.add(key)
            del pending[key]
    return ordered


@router.get("/api/meal-cycles/{cycle_id}/cooking-mode", response_model=CycleCookingModeResponse)
def cycle_cooking_mode(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = db.scalar(select(MealCycle).where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID).options(selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition), selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal)))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    planned = [slot.planned_meal for slot in cycle.slots if slot.planned_meal is not None]
    recipe_ids = {int(component["recipe_id"]) for meal in planned for component in json.loads(meal.scaled_components or "[]") if component.get("recipe_id") is not None}
    recipes = list(db.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids)).options(selectinload(Recipe.cooking_steps), selectinload(Recipe.prep_groups), selectinload(Recipe.ingredients))).unique()) if recipe_ids else []
    recipe_map = {recipe.id: recipe for recipe in recipes}
    all_step_ids = [step.id for recipe in recipes for step in recipe.cooking_steps]
    timers_by_step = _timer_rows(db, all_step_ids)
    equipment_by_step = _equipment_rows(db, all_step_ids)
    temperatures_by_step = _temperature_rows(db, all_step_ids)
    coordination_by_step = _coordination_rows(db, all_step_ids)
    dependencies_by_step = _dependency_rows(db, all_step_ids)
    all_timer_ids = [timer.id for rows in timers_by_step.values() for timer in rows]
    planned_ids = [meal.id for meal in planned]
    runtimes = list(db.scalars(select(PlannedCookingTimer).where(PlannedCookingTimer.planned_meal_id.in_(planned_ids), PlannedCookingTimer.cooking_timer_id.in_(all_timer_ids)))) if planned_ids and all_timer_ids else []
    runtime_map = {(row.planned_meal_id, row.cooking_timer_id): row for row in runtimes}
    ingredient_ids = {int(ingredient["ingredient_id"]) for meal in planned for component in json.loads(meal.scaled_components or "[]") for ingredient in component.get("ingredients", [])}
    unit_ids = {int(ingredient["unit_id"]) for meal in planned for component in json.loads(meal.scaled_components or "[]") for ingredient in component.get("ingredients", [])}
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
                no_steps.append(recipe_name); continue
            group_names = {group.id: group.name for group in recipe.prep_groups}
            ingredient_rows = {item.id: item for item in recipe.ingredients}
            component_ingredients = [{"scaled": scaled, "recipe_ingredient": ingredient_rows.get(int(scaled.get("recipe_ingredient_id") or 0))} for scaled in component.get("ingredients", [])]
            for step in recipe.cooking_steps:
                visible = component_ingredients if step.prep_group_id is None else [row for row in component_ingredients if row["recipe_ingredient"] is not None and row["recipe_ingredient"].prep_group_id == step.prep_group_id]
                timer_payloads = []
                for timer in timers_by_step.get(step.id, []):
                    runtime = runtime_map.get((meal.id, timer.id))
                    before = (runtime.status, runtime.remaining_seconds, runtime.ends_at_epoch) if runtime else None
                    item = _runtime_payload(timer, runtime, now)
                    after = (runtime.status, runtime.remaining_seconds, runtime.ends_at_epoch) if runtime else None
                    runtime_changed = runtime_changed or before != after
                    if item["status"] != "DISMISSED": timer_payloads.append(item)
                meta = coordination_by_step.get(step.id)
                flat_steps.append({
                    "step_id": step.id, "component_index": component_index, "meal_recipe_id": int(component.get("meal_recipe_id") or -(component_index + 1)), "recipe_id": recipe_id, "recipe_name": recipe_name,
                    "title": step.title, "instructions": step.instructions, "prep_group_id": step.prep_group_id, "prep_group_name": group_names.get(step.prep_group_id) if step.prep_group_id is not None else None,
                    "ingredients": [{"ingredient_id": int(row["scaled"]["ingredient_id"]), "ingredient_name": ingredient_names.get(int(row["scaled"]["ingredient_id"]), f"Ingredient {row['scaled']['ingredient_id']}"), "quantity": Decimal(str(row["scaled"]["quantity"])), "unit_id": int(row["scaled"]["unit_id"]), "unit_code": unit_codes.get(int(row["scaled"]["unit_id"]), str(row["scaled"]["unit_id"])), "preparation": row["recipe_ingredient"].preparation if row["recipe_ingredient"] else None, "prep_method": row["recipe_ingredient"].prep_method if row["recipe_ingredient"] else None, "prep_size": row["recipe_ingredient"].prep_size if row["recipe_ingredient"] else None, "prep_state": row["recipe_ingredient"].prep_state if row["recipe_ingredient"] else None} for row in visible],
                    "timers": timer_payloads, "equipment": equipment_by_step.get(step.id, []), "temperatures": [_temperature_payload(row) for row in temperatures_by_step.get(step.id, [])],
                    "coordination_stage": meta.stage if meta else 0, "parallel_capable": bool(meta.parallel_capable) if meta else False, "parallel_group": None, "source_sort_order": step.sort_order,
                })
        relevant_ids = {row["step_id"] for row in flat_steps}
        coordinated = any(step_id in coordination_by_step or dependencies_by_step.get(step_id) for step_id in relevant_ids)
        flat_steps = _coordinate_steps(flat_steps, dependencies_by_step, coordination_by_step)
        total = len(flat_steps)
        for index, row in enumerate(flat_steps):
            row["step_number"] = index + 1; row["total_steps"] = total; row.pop("source_sort_order", None)
        result_meals.append({"planned_meal_id": meal.id, "day_number": slot.day_number, "slot_label": slot.slot_definition.label, "meal_name": meal.snapshot_name, "planned_servings": meal.planned_servings, "planned_leftover_servings": meal.planned_leftover_servings, "steps": flat_steps, "components_without_steps": no_steps, "coordinated": coordinated})
    if runtime_changed: db.commit()
    return {"cycle_id": cycle_id, "meals": result_meals}
