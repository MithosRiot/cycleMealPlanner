from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.recipe import Recipe
from app.models.reference import MeasurementUnit
from app.schemas.combined_prep import CombinedPrepRead

router = APIRouter(prefix="/api/meal-cycles", tags=["combined-prep"])
HOUSEHOLD_ID = 1


def _text(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _json_list(raw: str | None) -> list[dict]:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


@router.get("/{cycle_id}/combined-prep", response_model=CombinedPrepRead)
def get_combined_prep(cycle_id: int, db: Session = Depends(get_db)) -> dict:
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

    placements = [slot.planned_meal for slot in cycle.slots if slot.planned_meal is not None]
    recipe_ids: set[int] = set()
    for placement in placements:
        for component in _json_list(placement.scaled_components):
            if component.get("recipe_id") is not None:
                recipe_ids.add(int(component["recipe_id"]))
        for component in _json_list(placement.snapshot_components):
            if component.get("recipe_id") is not None:
                recipe_ids.add(int(component["recipe_id"]))

    recipes = list(db.scalars(
        select(Recipe)
        .where(Recipe.id.in_(recipe_ids))
        .options(selectinload(Recipe.ingredients), selectinload(Recipe.prep_groups), selectinload(Recipe.advance_prep))
    ).unique()) if recipe_ids else []
    recipe_map = {recipe.id: recipe for recipe in recipes}
    ingredient_ids = {item.ingredient_id for recipe in recipes for item in recipe.ingredients}
    ingredients = {item.id: item for item in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids)))} if ingredient_ids else {}
    units = {item.id: item for item in db.scalars(select(MeasurementUnit))}

    ingredient_rows: list[dict] = []
    advance_rows: list[dict] = []

    for slot in sorted(cycle.slots, key=lambda row: (row.day_number, row.sort_order, row.id)):
        placement = slot.planned_meal
        if placement is None:
            continue

        ingredient_groups: dict[tuple, dict] = {}
        for component in _json_list(placement.scaled_components):
            recipe = recipe_map.get(int(component.get("recipe_id", 0)))
            if recipe is None:
                continue
            meal_recipe_id = int(component.get("meal_recipe_id") or 0)
            recipe_ingredients = {row.id: row for row in recipe.ingredients}
            group_names = {row.id: row.name for row in recipe.prep_groups}
            for scaled in component.get("ingredients", []):
                recipe_ingredient = recipe_ingredients.get(int(scaled.get("recipe_ingredient_id") or 0))
                if recipe_ingredient is None:
                    continue
                ingredient = ingredients.get(int(scaled["ingredient_id"]))
                source_unit = units.get(int(scaled["unit_id"]))
                if ingredient is None or source_unit is None:
                    continue
                group_name = group_names.get(recipe_ingredient.prep_group_id) if recipe_ingredient.prep_group_id else None
                key = (
                    placement.id,
                    ingredient.id,
                    _text(group_name),
                    _text(recipe_ingredient.preparation),
                    _text(recipe_ingredient.prep_method),
                    _text(recipe_ingredient.prep_size),
                    _text(recipe_ingredient.prep_state),
                    source_unit.unit_family,
                )
                quantity = Decimal(str(scaled.get("quantity", "0")))
                if quantity <= 0:
                    continue
                existing = ingredient_groups.get(key)
                if existing is None:
                    existing = {
                        "planned_meal_id": placement.id,
                        "meal_name": placement.snapshot_name,
                        "day_number": slot.day_number,
                        "slot_label": slot.slot_definition.label,
                        "ingredient_id": ingredient.id,
                        "ingredient_name": ingredient.name,
                        "prep_group_name": group_name,
                        "preparation": recipe_ingredient.preparation,
                        "prep_method": recipe_ingredient.prep_method,
                        "prep_size": recipe_ingredient.prep_size,
                        "prep_state": recipe_ingredient.prep_state,
                        "quantity": Decimal("0"),
                        "unit_id": source_unit.id,
                        "unit_code": source_unit.code,
                        "base_multiplier": Decimal(source_unit.base_multiplier),
                        "sources": [],
                    }
                    ingredient_groups[key] = existing
                output_unit = units[existing["unit_id"]]
                base_quantity = quantity * Decimal(source_unit.base_multiplier)
                converted = base_quantity / Decimal(output_unit.base_multiplier)
                existing["quantity"] += converted
                existing["sources"].append({
                    "planned_meal_id": placement.id,
                    "meal_recipe_id": meal_recipe_id,
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "recipe_ingredient_id": recipe_ingredient.id,
                    "quantity": quantity,
                    "unit_code": source_unit.code,
                })
        for row in ingredient_groups.values():
            row.pop("base_multiplier", None)
            ingredient_rows.append(row)

        task_groups: dict[tuple, dict] = {}
        serving_datetime = placement.scheduled_datetime
        for component in _json_list(placement.snapshot_components):
            recipe = recipe_map.get(int(component.get("recipe_id", 0)))
            if recipe is None:
                continue
            meal_recipe_id = int(component.get("meal_recipe_id") or 0)
            group_names = {row.id: row.name for row in recipe.prep_groups}
            for prep in recipe.advance_prep:
                group_name = group_names.get(prep.prep_group_id) if prep.prep_group_id else None
                start_datetime = serving_datetime - timedelta(minutes=prep.lead_time_minutes) if serving_datetime else None
                end_datetime = start_datetime + timedelta(minutes=prep.duration_minutes) if start_datetime and prep.duration_minutes is not None else start_datetime
                reminder_at = start_datetime - timedelta(minutes=prep.reminder_offset_minutes or 0) if prep.reminder_enabled and start_datetime is not None else None
                key = (
                    placement.id, prep.task_type, _text(prep.title), _text(prep.instructions), _text(group_name),
                    prep.lead_time_minutes, prep.duration_minutes, prep.reminder_enabled, prep.reminder_offset_minutes,
                )
                existing = task_groups.get(key)
                if existing is None:
                    existing = {
                        "planned_meal_id": placement.id,
                        "meal_name": placement.snapshot_name,
                        "day_number": slot.day_number,
                        "slot_label": slot.slot_definition.label,
                        "task_type": prep.task_type,
                        "title": prep.title,
                        "instructions": prep.instructions,
                        "prep_group_name": group_name,
                        "lead_time_minutes": prep.lead_time_minutes,
                        "duration_minutes": prep.duration_minutes,
                        "serving_datetime": serving_datetime,
                        "start_datetime": start_datetime,
                        "end_datetime": end_datetime,
                        "reminder_enabled": prep.reminder_enabled,
                        "reminder_offset_minutes": prep.reminder_offset_minutes,
                        "reminder_at": reminder_at,
                        "sources": [],
                    }
                    task_groups[key] = existing
                existing["sources"].append({
                    "planned_meal_id": placement.id,
                    "meal_recipe_id": meal_recipe_id,
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "advance_prep_id": prep.id,
                })
        advance_rows.extend(task_groups.values())

    ingredient_rows.sort(key=lambda row: (row["day_number"], row["slot_label"], row["prep_group_name"] or "", row["ingredient_name"]))
    advance_rows.sort(key=lambda row: (row["start_datetime"] is None, row["start_datetime"] or row["serving_datetime"], row["meal_name"], row["title"]))
    return {
        "meal_cycle_id": cycle.id,
        "meal_cycle_name": cycle.name,
        "ingredient_prep": ingredient_rows,
        "advance_prep": advance_rows,
    }
