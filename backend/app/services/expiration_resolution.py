from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.engines.recipe_scaling import scale_quantity
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.meal import Meal
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.recipe import Recipe
from app.models.reference import InventoryLocation, MeasurementUnit
from app.services.dashboard_use_soon import use_soon_rows
from app.services.inventory_availability import availability_for

HOUSEHOLD_ID = 1
ACTION_ORDER = {
    "MOVE_EXISTING": 0,
    "PLAN_MEAL": 1,
    "PLAN_RECIPE": 2,
    "PLAN_PRODUCED": 3,
    "FREEZE": 4,
}


def _slot_date(cycle: MealCycle, slot: CycleSlot) -> date | None:
    if cycle.start_date is None:
        return None
    return cycle.start_date + timedelta(days=slot.day_number - 1)


def _slot_key(slot: CycleSlot) -> tuple:
    return (slot.day_number, slot.sort_order, slot.id)


def _slot_label(slot: CycleSlot) -> str:
    return slot.slot_definition.label.strip().upper().replace(" ", "_")


def _compatible_slot(slot: CycleSlot, meal_types: set[str]) -> bool:
    return not meal_types or _slot_label(slot) in meal_types


def _eligible_empty_slots(cycle: MealCycle, today: date, deadline: date, meal_types: set[str]) -> list[CycleSlot]:
    return [
        slot
        for slot in sorted(cycle.slots, key=_slot_key)
        if slot.planned_meal is None
        and (scheduled := _slot_date(cycle, slot)) is not None
        and today <= scheduled <= deadline
        and _compatible_slot(slot, meal_types)
    ]


def _recipe_requirements(recipe: Recipe, requested_servings: Decimal) -> list[tuple[int, Decimal, int]]:
    scale_factor = requested_servings / Decimal(recipe.base_servings)
    rows: list[tuple[int, Decimal, int]] = []
    for ingredient in recipe.ingredients:
        quantity, _ = scale_quantity(Decimal(ingredient.quantity), scale_factor, ingredient.scaling_mode)
        if quantity > 0:
            rows.append((ingredient.ingredient_id, quantity, ingredient.unit_id))
    return rows


def _meal_requirements(db: Session, meal: Meal) -> list[tuple[int, Decimal, int]]:
    rows: list[tuple[int, Decimal, int]] = []
    for component in meal.recipes:
        recipe = db.scalar(
            select(Recipe)
            .where(Recipe.id == component.recipe_id, Recipe.household_id == HOUSEHOLD_ID, Recipe.active.is_(True))
            .options(selectinload(Recipe.ingredients))
        )
        if recipe is None:
            continue
        requested_servings = Decimal("4") * Decimal(component.serving_multiplier)
        rows.extend(_recipe_requirements(recipe, requested_servings))
    return rows


def _candidate_score(
    db: Session,
    requirements: list[tuple[int, Decimal, int]],
    expiring_ingredient_ids: set[int],
    target_ingredient_id: int,
    units: dict[int, MeasurementUnit],
    cycle_id: int,
) -> tuple[int, int, Decimal] | None:
    matched = {ingredient_id for ingredient_id, quantity, _ in requirements if quantity > 0 and ingredient_id in expiring_ingredient_ids}
    if target_ingredient_id not in matched:
        return None

    shortage_lines = 0
    shortage_ratio = Decimal("0")
    by_ingredient_unit: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    for ingredient_id, quantity, unit_id in requirements:
        by_ingredient_unit[(ingredient_id, unit_id)] += quantity

    for (ingredient_id, unit_id), required in by_ingredient_unit.items():
        unit = units.get(unit_id)
        if unit is None or required <= 0:
            continue
        _, _, available, _ = availability_for(
            db,
            ingredient_id,
            unit.unit_family,
            unit,
            exclude_cycle_id=cycle_id,
            units=units,
        )
        if available < required:
            shortage_lines += 1
            shortage_ratio += (required - available) / required

    return len(matched), shortage_lines, shortage_ratio


def _planned_ingredient_ids(planned) -> set[int]:
    result: set[int] = set()
    try:
        components = json.loads(planned.scaled_components or "[]")
    except json.JSONDecodeError:
        return result
    for component in components:
        for row in component.get("ingredients", []):
            ingredient_id = row.get("ingredient_id")
            if ingredient_id is not None:
                result.add(int(ingredient_id))
    return result


def expiration_resolution_rows(
    db: Session,
    cycle_id: int,
    horizon_days: int = 7,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(
            selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal),
            selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition),
        )
    )
    if cycle is None:
        raise ValueError("Meal cycle not found")
    if cycle.status not in {"DRAFT", "ACTIVE"}:
        raise ValueError("Expiration resolutions require a DRAFT or ACTIVE Meal Cycle")
    if cycle.start_date is None:
        raise ValueError("Set a cycle start date to resolve expiration timing")

    units = {row.id: row for row in db.scalars(select(MeasurementUnit))}
    ingredients = {
        row.id: row
        for row in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    freezer = db.scalar(
        select(InventoryLocation)
        .where(
            InventoryLocation.household_id == HOUSEHOLD_ID,
            InventoryLocation.active.is_(True),
            InventoryLocation.location_type == "FREEZER",
        )
        .order_by(InventoryLocation.sort_order, InventoryLocation.id)
    )

    use_soon = use_soon_rows(db, horizon_days=horizon_days, today=today)
    expiring_ingredient_ids = {
        int(row["ingredient_id"])
        for row in use_soon
        if row["source_type"] == "INGREDIENT" and row["ingredient_id"] is not None
    }

    recipes = list(db.scalars(
        select(Recipe)
        .where(Recipe.household_id == HOUSEHOLD_ID, Recipe.active.is_(True))
        .options(selectinload(Recipe.ingredients), selectinload(Recipe.meal_types))
        .order_by(Recipe.name, Recipe.id)
    ))
    meals = list(db.scalars(
        select(Meal)
        .where(Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True))
        .options(selectinload(Meal.recipes), selectinload(Meal.meal_types))
        .order_by(Meal.name, Meal.id)
    ))

    resolutions: list[dict] = []
    for row in use_soon:
        lot = db.get(InventoryLot, row["lot_id"])
        if lot is None:
            continue
        actions: list[dict] = []
        deadline = row["expiration_date"]

        if row["source_type"] == "INGREDIENT" and row["ingredient_id"] is not None:
            ingredient_id = int(row["ingredient_id"])

            for source_slot in sorted(cycle.slots, key=_slot_key):
                planned = source_slot.planned_meal
                source_date = _slot_date(cycle, source_slot)
                if planned is None or planned.locked or source_date is None or ingredient_id not in _planned_ingredient_ids(planned):
                    continue
                earlier = [
                    target
                    for target in sorted(cycle.slots, key=_slot_key)
                    if target.planned_meal is None
                    and target.sort_order == source_slot.sort_order
                    and (target_date := _slot_date(cycle, target)) is not None
                    and today <= target_date <= deadline
                    and target_date < source_date
                ]
                if not earlier:
                    continue
                target = earlier[0]
                actions.append({
                    "kind": "MOVE_EXISTING",
                    "title": f"Move {planned.snapshot_name} earlier",
                    "detail": f"Move Day {source_slot.day_number} to Day {target.day_number} so it can use {row['source_name']} before expiration.",
                    "candidate_name": planned.snapshot_name,
                    "source_slot_id": source_slot.id,
                    "source_day_number": source_slot.day_number,
                    "target_slot_id": target.id,
                    "target_day_number": target.day_number,
                    "matched_expiring_items": 1,
                    "shopping_shortage_lines": 0,
                    "shopping_shortage_ratio": "0",
                })

            recipe_candidates: list[tuple[tuple, dict]] = []
            for recipe in recipes:
                requirements = _recipe_requirements(recipe, Decimal(recipe.base_servings))
                score = _candidate_score(db, requirements, expiring_ingredient_ids, ingredient_id, units, cycle.id)
                if score is None:
                    continue
                meal_types = {item.meal_type for item in recipe.meal_types}
                targets = _eligible_empty_slots(cycle, today, deadline, meal_types)
                if not targets:
                    continue
                target = targets[0]
                matched_count, shortage_lines, shortage_ratio = score
                action = {
                    "kind": "PLAN_RECIPE",
                    "title": f"Plan Recipe: {recipe.name}",
                    "detail": f"Uses {matched_count} expiring item{'s' if matched_count != 1 else ''}; {shortage_lines} additional Shopping line{'s' if shortage_lines != 1 else ''} estimated.",
                    "candidate_name": recipe.name,
                    "recipe_id": recipe.id,
                    "planned_servings": str(recipe.base_servings),
                    "target_slot_id": target.id,
                    "target_day_number": target.day_number,
                    "matched_expiring_items": matched_count,
                    "shopping_shortage_lines": shortage_lines,
                    "shopping_shortage_ratio": str(shortage_ratio),
                }
                recipe_candidates.append(((-matched_count, shortage_lines, shortage_ratio, recipe.name.casefold(), recipe.id), action))
            actions.extend(action for _, action in sorted(recipe_candidates, key=lambda item: item[0])[:2])

            meal_candidates: list[tuple[tuple, dict]] = []
            for meal in meals:
                requirements = _meal_requirements(db, meal)
                score = _candidate_score(db, requirements, expiring_ingredient_ids, ingredient_id, units, cycle.id)
                if score is None:
                    continue
                meal_types = {item.meal_type for item in meal.meal_types}
                targets = _eligible_empty_slots(cycle, today, deadline, meal_types)
                if not targets:
                    continue
                target = targets[0]
                matched_count, shortage_lines, shortage_ratio = score
                action = {
                    "kind": "PLAN_MEAL",
                    "title": f"Plan Meal: {meal.name}",
                    "detail": f"Uses {matched_count} expiring item{'s' if matched_count != 1 else ''}; {shortage_lines} additional Shopping line{'s' if shortage_lines != 1 else ''} estimated.",
                    "candidate_name": meal.name,
                    "meal_id": meal.id,
                    "target_slot_id": target.id,
                    "target_day_number": target.day_number,
                    "matched_expiring_items": matched_count,
                    "shopping_shortage_lines": shortage_lines,
                    "shopping_shortage_ratio": str(shortage_ratio),
                }
                meal_candidates.append(((-matched_count, shortage_lines, shortage_ratio, meal.name.casefold(), meal.id), action))
            actions.extend(action for _, action in sorted(meal_candidates, key=lambda item: item[0])[:2])

            ingredient = ingredients.get(ingredient_id)
            if ingredient is not None and ingredient.perishable and freezer is not None and lot.frozen_date is None:
                actions.append({
                    "kind": "FREEZE",
                    "title": f"Freeze {row['source_name']}",
                    "detail": f"Move Lot {lot.id} to {freezer.name} and mark it frozen. It will leave Use Soon until thawed.",
                    "candidate_name": row["source_name"],
                    "freezer_location_id": freezer.id,
                    "freezer_location_name": freezer.name,
                    "matched_expiring_items": 1,
                    "shopping_shortage_lines": 0,
                    "shopping_shortage_ratio": "0",
                })
        else:
            targets = _eligible_empty_slots(cycle, today, deadline, set())
            if targets:
                target = targets[0]
                actions.append({
                    "kind": "PLAN_PRODUCED",
                    "title": f"Plan {row['source_name']}",
                    "detail": f"Use the available produced stock on Day {target.day_number} before it expires.",
                    "candidate_name": row["source_name"],
                    "lot_id": lot.id,
                    "target_slot_id": target.id,
                    "target_day_number": target.day_number,
                    "quantity": str(row["available_quantity"]),
                    "matched_expiring_items": 1,
                    "shopping_shortage_lines": 0,
                    "shopping_shortage_ratio": "0",
                })

        actions.sort(key=lambda action: (
            ACTION_ORDER.get(action["kind"], 99),
            -int(action.get("matched_expiring_items", 0)),
            int(action.get("shopping_shortage_lines", 0)),
            Decimal(str(action.get("shopping_shortage_ratio", "0"))),
            str(action.get("candidate_name", "")).casefold(),
            int(action.get("target_day_number", 999999)),
        ))

        resolutions.append({
            **row,
            "status": "ACTIONABLE" if actions else "NO_SUGGESTION",
            "no_suggestion_reason": None if actions else "No compatible Meal, Recipe, produced-stock placement, move, or safe freeze resolution is currently available.",
            "actions": actions,
        })

    return {
        "meal_cycle_id": cycle.id,
        "meal_cycle_name": cycle.name,
        "horizon_days": horizon_days,
        "resolutions": resolutions,
    }
