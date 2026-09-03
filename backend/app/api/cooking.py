from __future__ import annotations

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.recipe import Recipe, RecipeCookingStep, RecipePrepGroup
from app.models.reference import MeasurementUnit
from app.schemas.cooking import CookingStepInput, CookingStepRead, CycleCookingModeResponse

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


def _step_payload(step: RecipeCookingStep, group_names: dict[int, str]) -> dict:
    return {
        "id": step.id,
        "recipe_id": step.recipe_id,
        "prep_group_id": step.prep_group_id,
        "prep_group_name": group_names.get(step.prep_group_id) if step.prep_group_id is not None else None,
        "title": step.title,
        "instructions": step.instructions,
        "sort_order": step.sort_order,
    }


@router.get("/api/recipes/{recipe_id}/cooking-steps", response_model=list[CookingStepRead])
def list_cooking_steps(recipe_id: int, db: Session = Depends(get_db)) -> list[dict]:
    recipe = _recipe_or_404(db, recipe_id)
    groups = {group.id: group.name for group in recipe.prep_groups}
    return [_step_payload(step, groups) for step in recipe.cooking_steps]


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
        recipe.cooking_steps.append(RecipeCookingStep(
            prep_group_id=item.prep_group_id,
            title=item.title.strip(),
            instructions=item.instructions.strip() if item.instructions else None,
            sort_order=index,
        ))
    db.commit()
    recipe = _recipe_or_404(db, recipe_id)
    groups = {group.id: group.name for group in recipe.prep_groups}
    return [_step_payload(step, groups) for step in recipe.cooking_steps]


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
        .options(selectinload(Recipe.cooking_steps), selectinload(Recipe.prep_groups))
    ).unique()) if recipe_ids else []
    recipe_map = {recipe.id: recipe for recipe in recipes}

    ingredient_ids: set[int] = set()
    unit_ids: set[int] = set()
    for meal in planned:
        for component in json.loads(meal.scaled_components or "[]"):
            for ingredient in component.get("ingredients", []):
                ingredient_ids.add(int(ingredient["ingredient_id"]))
                unit_ids.add(int(ingredient["unit_id"]))
    ingredient_names = {item.id: item.name for item in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))} if ingredient_ids else {}
    unit_codes = {item.id: item.code for item in db.scalars(select(MeasurementUnit).where(MeasurementUnit.id.in_(unit_ids)))} if unit_ids else {}

    result_meals: list[dict] = []
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
            component_ingredients = component.get("ingredients", [])
            for step in recipe.cooking_steps:
                visible_ingredients = component_ingredients
                if step.prep_group_id is not None:
                    visible_ingredients = [row for row in component_ingredients if row.get("prep_group_id") == step.prep_group_id]
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
                        "ingredient_id": int(row["ingredient_id"]),
                        "ingredient_name": ingredient_names.get(int(row["ingredient_id"]), f"Ingredient {row['ingredient_id']}"),
                        "quantity": Decimal(str(row["quantity"])),
                        "unit_id": int(row["unit_id"]),
                        "unit_code": unit_codes.get(int(row["unit_id"]), str(row["unit_id"])),
                        "preparation": row.get("preparation"),
                        "prep_method": row.get("prep_method"),
                        "prep_size": row.get("prep_size"),
                        "prep_state": row.get("prep_state"),
                    } for row in visible_ingredients],
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

    return {"cycle_id": cycle_id, "meals": result_meals}
