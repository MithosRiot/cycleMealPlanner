import json
import random
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.engines.recipe_scaling import scale_quantity
from app.models.meal import Meal
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.recipe import Recipe
from app.schemas.planned_meal import (
    PlannedMealAssign,
    PlannedMealLock,
    PlannedMealMove,
    PlannedMealPlanningUpdate,
    PlannedMealRead,
    RandomFillResult,
)
from app.services.normalization import normalize_name

router = APIRouter(prefix="/api/meal-cycles", tags=["meal-placement"])
HOUSEHOLD_ID = 1
DEFAULT_SERVINGS = Decimal("4")


def _component_key(component: dict) -> int:
    stored_id = component.get("meal_recipe_id")
    if stored_id is not None:
        return int(stored_id)
    return -(int(component.get("sort_order", 0)) + 1)


def _load_slot(db: Session, cycle_id: int, slot_id: int) -> CycleSlot:
    slot = db.scalar(
        select(CycleSlot)
        .join(MealCycle)
        .where(CycleSlot.id == slot_id, CycleSlot.cycle_id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(selectinload(CycleSlot.slot_definition), selectinload(CycleSlot.planned_meal))
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Cycle slot not found")
    return slot


def _load_meal(db: Session, meal_id: int) -> Meal:
    meal = db.scalar(
        select(Meal)
        .where(Meal.id == meal_id, Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True))
        .options(selectinload(Meal.meal_types), selectinload(Meal.recipes), selectinload(Meal.tags))
    )
    if meal is None:
        raise HTTPException(status_code=400, detail="Active meal not found")
    return meal


def _snapshot(meal: Meal) -> dict[str, str | None]:
    components = [
        {
            "meal_recipe_id": component.id,
            "recipe_id": component.recipe_id,
            "serving_multiplier": str(component.serving_multiplier),
            "default_servings": str(component.default_servings) if component.default_servings is not None else None,
            "sort_order": component.sort_order,
            "notes": component.notes,
        }
        for component in meal.recipes
    ]
    return {
        "snapshot_name": meal.name,
        "snapshot_description": meal.description,
        "snapshot_meal_types": json.dumps([item.meal_type for item in meal.meal_types]),
        "snapshot_components": json.dumps(components),
    }


def _calculate_scaled_components(db: Session, planned: PlannedMeal) -> str:
    components = json.loads(planned.snapshot_components)
    overrides = {int(key): Decimal(str(value)) for key, value in json.loads(planned.component_serving_overrides).items()}
    total_servings = Decimal(planned.planned_servings) + Decimal(planned.planned_leftover_servings)
    results: list[dict] = []

    for component in components:
        component_id = _component_key(component)
        recipe = db.scalar(
            select(Recipe)
            .where(Recipe.id == int(component["recipe_id"]), Recipe.household_id == HOUSEHOLD_ID)
            .options(selectinload(Recipe.ingredients))
        )
        if recipe is None:
            raise HTTPException(status_code=409, detail=f"Recipe {component['recipe_id']} no longer exists")

        requested_servings = overrides.get(
            component_id,
            total_servings * Decimal(str(component["serving_multiplier"])),
        )
        if requested_servings <= 0:
            raise HTTPException(status_code=422, detail="Component serving overrides must be greater than zero")

        scale_factor = requested_servings / Decimal(recipe.base_servings)
        ingredients: list[dict] = []
        for ingredient in recipe.ingredients:
            quantity, manual_review = scale_quantity(
                Decimal(ingredient.quantity), scale_factor, ingredient.scaling_mode
            )
            ingredients.append(
                {
                    "recipe_ingredient_id": ingredient.id,
                    "ingredient_id": ingredient.ingredient_id,
                    "quantity": str(quantity),
                    "unit_id": ingredient.unit_id,
                    "scaling_mode": ingredient.scaling_mode,
                    "manual_review": manual_review,
                }
            )

        results.append(
            {
                "meal_recipe_id": component_id,
                "recipe_id": recipe.id,
                "base_servings": str(recipe.base_servings),
                "requested_servings": str(requested_servings),
                "scale_factor": str(scale_factor),
                "ingredients": ingredients,
            }
        )

    return json.dumps(results)


def _place(db: Session, slot: CycleSlot, meal: Meal) -> PlannedMeal:
    if slot.planned_meal is not None:
        if slot.planned_meal.locked:
            raise HTTPException(status_code=409, detail="Placement is locked")
        db.delete(slot.planned_meal)
        db.flush()
    planned = PlannedMeal(
        cycle_slot_id=slot.id,
        meal_id=meal.id,
        locked=False,
        planned_servings=DEFAULT_SERVINGS,
        planned_leftover_servings=Decimal("0"),
        component_serving_overrides="{}",
        **_snapshot(meal),
    )
    db.add(planned)
    db.flush()
    planned.scaled_components = _calculate_scaled_components(db, planned)
    db.flush()
    return planned


def _parse_json_dict(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _filter_by_population_rules(meals: list[Meal], slot_label: str, rules: dict) -> list[Meal]:
    global_include = {int(value) for value in rules.get("include_meal_ids", [])}
    global_exclude = {int(value) for value in rules.get("exclude_meal_ids", [])}
    slot_rule = rules.get("slot_rules", {}).get(normalize_name(slot_label), {})
    slot_include = {int(value) for value in slot_rule.get("include_meal_ids", [])}
    slot_exclude = {int(value) for value in slot_rule.get("exclude_meal_ids", [])}

    eligible = meals
    if global_include:
        eligible = [meal for meal in eligible if meal.id in global_include]
    eligible = [meal for meal in eligible if meal.id not in global_exclude]
    if slot_include:
        eligible = [meal for meal in eligible if meal.id in slot_include]
    return [meal for meal in eligible if meal.id not in slot_exclude]


def _repeat_spaced(eligible: list[Meal], day_number: int, spacing: int, placements: list[tuple[int, int]]) -> list[Meal]:
    if spacing <= 0:
        return eligible
    allowed = [
        meal for meal in eligible
        if all(existing_meal_id != meal.id or abs(existing_day - day_number) > spacing for existing_day, existing_meal_id in placements)
    ]
    return allowed or eligible


def _history_counts(db: Session, current_cycle_id: int) -> dict[int, int]:
    rows = db.execute(
        select(PlannedMeal.meal_id, func.count(PlannedMeal.id))
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .join(MealCycle, MealCycle.id == CycleSlot.cycle_id)
        .where(MealCycle.household_id == HOUSEHOLD_ID, MealCycle.id != current_cycle_id)
        .group_by(PlannedMeal.meal_id)
    ).all()
    return {int(meal_id): int(count) for meal_id, count in rows}


def _meal_weight(meal: Meal, preferences: dict, history_counts: dict[int, int]) -> float:
    weight = 1.0
    favorite_boost = float(preferences.get("favorite_boost", 1.0) or 1.0)
    if meal.favorite:
        weight *= max(1.0, favorite_boost)

    tag_weights = {int(tag_id): float(value) for tag_id, value in preferences.get("tag_weights", {}).items()}
    for tag in meal.tags:
        if tag.id in tag_weights:
            weight *= max(0.01, tag_weights[tag.id])

    history_penalty = min(max(float(preferences.get("history_penalty", 0.0) or 0.0), 0.0), 1.0)
    prior_count = history_counts.get(meal.id, 0)
    if prior_count and history_penalty:
        weight /= 1.0 + (prior_count * history_penalty)
    return max(weight, 0.000001)


@router.post("/{cycle_id}/slots/{slot_id}/planned-meal", response_model=PlannedMealRead, status_code=status.HTTP_201_CREATED)
def assign_meal(cycle_id: int, slot_id: int, payload: PlannedMealAssign, db: Session = Depends(get_db)) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    meal = _load_meal(db, payload.meal_id)
    planned = _place(db, slot, meal)
    db.commit()
    db.refresh(planned)
    return planned


@router.put("/{cycle_id}/slots/{slot_id}/planned-meal/planning", response_model=PlannedMealRead)
def update_planning(cycle_id: int, slot_id: int, payload: PlannedMealPlanningUpdate, db: Session = Depends(get_db)) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    if slot.planned_meal is None:
        raise HTTPException(status_code=404, detail="No planned meal in this slot")

    valid_component_ids = {_component_key(component) for component in json.loads(slot.planned_meal.snapshot_components)}
    unknown = set(payload.component_serving_overrides) - valid_component_ids
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown planned component: {min(unknown)}")

    slot.planned_meal.planned_servings = payload.planned_servings
    slot.planned_meal.planned_leftover_servings = payload.planned_leftover_servings
    slot.planned_meal.component_serving_overrides = json.dumps(
        {str(key): str(value) for key, value in payload.component_serving_overrides.items()}
    )
    slot.planned_meal.scaled_components = _calculate_scaled_components(db, slot.planned_meal)
    db.commit()
    db.refresh(slot.planned_meal)
    return slot.planned_meal


@router.delete("/{cycle_id}/slots/{slot_id}/planned-meal", status_code=status.HTTP_204_NO_CONTENT)
def remove_meal(cycle_id: int, slot_id: int, db: Session = Depends(get_db)) -> None:
    slot = _load_slot(db, cycle_id, slot_id)
    if slot.planned_meal is None:
        return
    if slot.planned_meal.locked:
        raise HTTPException(status_code=409, detail="Placement is locked")
    db.delete(slot.planned_meal)
    db.commit()


@router.put("/{cycle_id}/slots/{slot_id}/planned-meal/lock", response_model=PlannedMealRead)
def set_lock(cycle_id: int, slot_id: int, payload: PlannedMealLock, db: Session = Depends(get_db)) -> PlannedMeal:
    slot = _load_slot(db, cycle_id, slot_id)
    if slot.planned_meal is None:
        raise HTTPException(status_code=404, detail="No planned meal in this slot")
    slot.planned_meal.locked = payload.locked
    db.commit()
    db.refresh(slot.planned_meal)
    return slot.planned_meal


@router.post("/{cycle_id}/slots/{slot_id}/planned-meal/move", response_model=PlannedMealRead)
def move_meal(cycle_id: int, slot_id: int, payload: PlannedMealMove, db: Session = Depends(get_db)) -> PlannedMeal:
    source = _load_slot(db, cycle_id, slot_id)
    target = _load_slot(db, cycle_id, payload.target_cycle_slot_id)
    if source.planned_meal is None:
        raise HTTPException(status_code=404, detail="No planned meal in source slot")
    if source.planned_meal.locked:
        raise HTTPException(status_code=409, detail="Placement is locked")
    if target.planned_meal is not None:
        raise HTTPException(status_code=409, detail="Target slot is occupied")
    planned = source.planned_meal
    planned.cycle_slot_id = target.id
    db.commit()
    db.refresh(planned)
    return planned


@router.post("/{cycle_id}/random-fill", response_model=RandomFillResult)
def random_fill(cycle_id: int, db: Session = Depends(get_db)) -> RandomFillResult:
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

    meals = list(
        db.scalars(
            select(Meal)
            .where(Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True))
            .options(selectinload(Meal.meal_types), selectinload(Meal.recipes), selectinload(Meal.tags))
        ).unique()
    )
    if not meals:
        return RandomFillResult(filled_count=0)

    rules = _parse_json_dict(cycle.population_rules)
    preferences = _parse_json_dict(cycle.smart_preferences)
    repeat_spacing = int(preferences.get("repeat_spacing_days", 0) or 0)
    history_counts = _history_counts(db, cycle.id)
    placements = [
        (slot.day_number, slot.planned_meal.meal_id)
        for slot in cycle.slots
        if slot.planned_meal is not None
    ]

    filled = 0
    for slot in sorted(cycle.slots, key=lambda value: (value.day_number, value.sort_order, value.id)):
        if slot.planned_meal is not None:
            continue
        label = slot.slot_definition.label.strip()
        label_key = normalize_name(label)
        typed = [meal for meal in meals if any(normalize_name(mt.meal_type) == label_key for mt in meal.meal_types)]
        eligible = _filter_by_population_rules(typed, label, rules)
        if not eligible:
            continue
        eligible = _repeat_spaced(eligible, slot.day_number, repeat_spacing, placements)
        weights = [_meal_weight(meal, preferences, history_counts) for meal in eligible]
        selected = random.choices(eligible, weights=weights, k=1)[0]
        _place(db, slot, selected)
        placements.append((slot.day_number, selected.id))
        filled += 1

    db.commit()
    return RandomFillResult(filled_count=filled)
