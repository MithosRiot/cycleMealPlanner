from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot
from app.models.meal import Meal
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.recipe import Recipe
from app.models.reference import MeasurementUnit
from app.services.normalization import normalize_name
from app.services.units import convert_quantity

router = APIRouter(prefix="/api/meal-cycles", tags=["cycle-validation"])
HOUSEHOLD_ID = 1


def _issue(severity: str, code: str, message: str, **context) -> dict:
    return {"severity": severity, "code": code, "message": message, "context": context}


def _load_cycle(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(
        select(MealCycle)
        .where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID)
        .options(
            selectinload(MealCycle.slot_definitions),
            selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition),
            selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal),
        )
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _parse_json(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _population_eligible(meal: Meal, slot_label: str, rules: dict) -> bool:
    global_include = {int(value) for value in rules.get("include_meal_ids", [])}
    global_exclude = {int(value) for value in rules.get("exclude_meal_ids", [])}
    slot_rule = rules.get("slot_rules", {}).get(normalize_name(slot_label), {})
    slot_include = {int(value) for value in slot_rule.get("include_meal_ids", [])}
    slot_exclude = {int(value) for value in slot_rule.get("exclude_meal_ids", [])}
    if global_include and meal.id not in global_include:
        return False
    if meal.id in global_exclude:
        return False
    if slot_include and meal.id not in slot_include:
        return False
    return meal.id not in slot_exclude


@router.get("/{cycle_id}/validate")
def validate_cycle(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    cycle = _load_cycle(db, cycle_id)
    issues: list[dict] = []
    units = {unit.id: unit for unit in db.scalars(select(MeasurementUnit))}
    ingredients = {
        ingredient.id: ingredient
        for ingredient in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))
    }
    active_meals = list(
        db.scalars(
            select(Meal)
            .where(Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True))
            .options(selectinload(Meal.meal_types))
        ).unique()
    )
    active_meal_ids = {meal.id for meal in active_meals}
    active_recipe_ids = set(db.scalars(select(Recipe.id).where(Recipe.household_id == HOUSEHOLD_ID, Recipe.active.is_(True))))

    inventory_by_ingredient: dict[int, list[InventoryLot]] = defaultdict(list)
    for lot in db.scalars(select(InventoryLot).where(InventoryLot.household_id == HOUSEHOLD_ID, InventoryLot.quantity > 0)):
        inventory_by_ingredient[lot.ingredient_id].append(lot)

    requirements: dict[tuple[int, str], dict] = {}
    for slot in sorted(cycle.slots, key=lambda value: (value.day_number, value.sort_order, value.id)):
        label = slot.slot_definition.label
        planned = slot.planned_meal
        if planned is None:
            issues.append(_issue("ERROR", "EMPTY_SLOT", f"Day {slot.day_number} · {label} has no planned Meal.", day_number=slot.day_number, slot_label=label, cycle_slot_id=slot.id))
            continue

        if planned.meal_id not in active_meal_ids:
            issues.append(_issue("ERROR", "MISSING_OR_ARCHIVED_MEAL", f"{planned.snapshot_name} references a missing or archived source Meal.", planned_meal_id=planned.id, meal_id=planned.meal_id, day_number=slot.day_number, slot_label=label))

        try:
            scaled_components = json.loads(planned.scaled_components or "[]")
        except json.JSONDecodeError:
            scaled_components = []
            issues.append(_issue("ERROR", "INVALID_SCALED_COMPONENTS", f"{planned.snapshot_name} has invalid persisted scaling data.", planned_meal_id=planned.id, day_number=slot.day_number, slot_label=label))

        for component in scaled_components:
            recipe_id = int(component.get("recipe_id", 0))
            if recipe_id not in active_recipe_ids:
                issues.append(_issue("ERROR", "MISSING_OR_ARCHIVED_RECIPE", f"{planned.snapshot_name} references missing or archived Recipe {recipe_id}.", planned_meal_id=planned.id, recipe_id=recipe_id, day_number=slot.day_number, slot_label=label))
            for row in component.get("ingredients", []):
                ingredient_id = int(row.get("ingredient_id", 0))
                quantity = Decimal(str(row.get("quantity", "0")))
                unit_id = int(row.get("unit_id", 0))
                unit = units.get(unit_id)
                ingredient = ingredients.get(ingredient_id)
                if ingredient is None:
                    issues.append(_issue("ERROR", "MISSING_INGREDIENT", f"{planned.snapshot_name} references missing Ingredient {ingredient_id}.", planned_meal_id=planned.id, ingredient_id=ingredient_id, day_number=slot.day_number, slot_label=label))
                    continue
                if unit is None:
                    issues.append(_issue("ERROR", "MISSING_UNIT", f"{ingredient.name} references missing measurement unit {unit_id}.", planned_meal_id=planned.id, ingredient_id=ingredient_id, unit_id=unit_id))
                    continue
                if quantity <= 0:
                    issues.append(_issue("ERROR", "INVALID_QUANTITY", f"{ingredient.name} has a non-positive planned quantity.", planned_meal_id=planned.id, ingredient_id=ingredient_id, quantity=str(quantity)))
                    continue
                if row.get("manual_review"):
                    issues.append(_issue("WARNING", "MANUAL_SCALING_REVIEW", f"{ingredient.name} uses MANUAL scaling and needs review.", planned_meal_id=planned.id, ingredient_id=ingredient_id, day_number=slot.day_number, slot_label=label))
                key = (ingredient_id, unit.unit_family)
                group = requirements.setdefault(key, {"ingredient": ingredient, "family": unit.unit_family, "rows": []})
                group["rows"].append((quantity, unit_id, planned.id, slot.day_number, label))

        if cycle.start_date is not None:
            planned_date = cycle.start_date + timedelta(days=slot.day_number - 1)
            ingredient_ids = {int(row.get("ingredient_id", 0)) for component in scaled_components for row in component.get("ingredients", [])}
            for ingredient_id in sorted(ingredient_ids):
                matching = inventory_by_ingredient.get(ingredient_id, [])
                if matching and all(lot.expiration_date is not None and lot.expiration_date < planned_date for lot in matching):
                    ingredient = ingredients.get(ingredient_id)
                    issues.append(_issue("WARNING", "EXPIRATION_RISK", f"All dated Inventory for {ingredient.name if ingredient else ingredient_id} expires before {planned.snapshot_name} is planned.", planned_meal_id=planned.id, ingredient_id=ingredient_id, day_number=slot.day_number, planned_date=str(planned_date)))

    families_by_ingredient: dict[int, set[str]] = defaultdict(set)
    for ingredient_id, family in requirements:
        families_by_ingredient[ingredient_id].add(family)
    for ingredient_id, families in families_by_ingredient.items():
        if len(families) > 1:
            ingredient = ingredients[ingredient_id]
            issues.append(_issue("WARNING", "INCOMPATIBLE_UNIT_FAMILIES", f"{ingredient.name} is required in incompatible measurement families and cannot be safely combined.", ingredient_id=ingredient_id, unit_families=sorted(families)))

    for (ingredient_id, family), group in sorted(requirements.items()):
        ingredient = group["ingredient"]
        preferred = units.get(ingredient.preferred_unit_id) if ingredient.preferred_unit_id else None
        target = preferred if preferred and preferred.unit_family == family else units[min(unit_id for _, unit_id, *_ in group["rows"])]
        required = sum((convert_quantity(quantity, units[unit_id], target) for quantity, unit_id, *_ in group["rows"]), Decimal("0"))
        available = Decimal("0")
        for lot in inventory_by_ingredient.get(ingredient_id, []):
            lot_unit = units.get(lot.unit_id)
            if lot_unit is not None and lot_unit.unit_family == family:
                available += convert_quantity(Decimal(lot.quantity), lot_unit, target)
        shortage = max(required - available, Decimal("0"))
        if shortage > 0:
            issues.append(_issue("WARNING", "INVENTORY_SHORTAGE", f"{ingredient.name} is short by {shortage} {target.code} for this cycle.", ingredient_id=ingredient_id, unit_family=family, required_quantity=str(required), inventory_quantity=str(available), shortage_quantity=str(shortage), unit_id=target.id, unit_code=target.code))

    rules = _parse_json(cycle.population_rules)
    for definition in cycle.slot_definitions:
        label_key = normalize_name(definition.label)
        typed = [meal for meal in active_meals if any(normalize_name(mt.meal_type) == label_key for mt in meal.meal_types)]
        eligible = [meal for meal in typed if _population_eligible(meal, definition.label, rules)]
        if not eligible:
            issues.append(_issue("WARNING", "NO_ELIGIBLE_MEALS", f"Population rules leave {definition.label} with no eligible active Meals.", slot_label=definition.label, slot_definition_id=definition.id))

    issues.sort(key=lambda item: (0 if item["severity"] == "ERROR" else 1, item["code"], json.dumps(item["context"], sort_keys=True)))
    error_count = sum(1 for item in issues if item["severity"] == "ERROR")
    warning_count = len(issues) - error_count
    return {
        "meal_cycle_id": cycle.id,
        "meal_cycle_name": cycle.name,
        "valid": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }
