from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.engines.recipe_scaling import scale_quantity
from app.models.equipment import Equipment
from app.models.ingredient import Ingredient, Tag
from app.models.recipe import (
    Recipe, RecipeAdvancePrep, RecipeEquipment, RecipeIngredient, RecipeIngredientSubstitution,
    RecipeMealType, RecipePrepGroup, RecipeVariant, RecipeVariantIngredientOverride,
)
from app.models.reference import MeasurementUnit
from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeScaleRequest, RecipeScaleResponse, RecipeUpdate
from app.services.normalization import normalize_name
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/recipes", tags=["recipes"])
DEFAULT_HOUSEHOLD_ID = 1
VALID_PREP_TASK_TYPES = {"PREP", "THAW", "MARINATE", "SOAK", "PROOF"}


def _recipe_statement():
    return select(Recipe).options(
        selectinload(Recipe.prep_groups),
        selectinload(Recipe.advance_prep),
        selectinload(Recipe.equipment),
        selectinload(Recipe.ingredients).selectinload(RecipeIngredient.substitutions),
        selectinload(Recipe.variants).selectinload(RecipeVariant.overrides),
        selectinload(Recipe.meal_types),
        selectinload(Recipe.tags),
    )


def _recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.scalar(_recipe_statement().where(Recipe.id == recipe_id, Recipe.household_id == DEFAULT_HOUSEHOLD_ID))
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _recipe_payload(recipe: Recipe) -> dict:
    return {
        "id": recipe.id, "household_id": recipe.household_id, "name": recipe.name,
        "description": recipe.description, "base_servings": recipe.base_servings,
        "serving_unit": recipe.serving_unit, "yield_quantity": recipe.yield_quantity,
        "yield_unit_id": recipe.yield_unit_id, "prep_time_minutes": recipe.prep_time_minutes,
        "cook_time_minutes": recipe.cook_time_minutes, "notes": recipe.notes,
        "favorite": recipe.favorite, "active": recipe.active,
        "meal_types": [item.meal_type for item in recipe.meal_types], "tags": recipe.tags,
        "prep_groups": recipe.prep_groups, "advance_prep": recipe.advance_prep,
        "equipment": recipe.equipment, "ingredients": recipe.ingredients,
    }


def _validate_recipe_references(db: Session, payload: RecipeCreate | RecipeUpdate) -> tuple[list[Tag], list[str]]:
    if payload.yield_unit_id is not None and db.get(MeasurementUnit, payload.yield_unit_id) is None:
        raise HTTPException(status_code=400, detail="Yield measurement unit not found")
    group_keys = [group.client_key.strip() for group in payload.prep_groups]
    if len(set(group_keys)) != len(group_keys):
        raise HTTPException(status_code=422, detail="Prep group keys must be unique")
    known_group_keys = set(group_keys)
    for item in payload.ingredients:
        ingredient = db.get(Ingredient, item.ingredient_id)
        if ingredient is None or ingredient.household_id != DEFAULT_HOUSEHOLD_ID:
            raise HTTPException(status_code=400, detail=f"Ingredient {item.ingredient_id} not found")
        if db.get(MeasurementUnit, item.unit_id) is None:
            raise HTTPException(status_code=400, detail=f"Measurement unit {item.unit_id} not found")
        if item.prep_group_key and item.prep_group_key not in known_group_keys:
            raise HTTPException(status_code=422, detail=f"Unknown prep group key {item.prep_group_key}")
        substitute_ids = [sub.substitute_ingredient_id for sub in item.substitutions]
        if len(set(substitute_ids)) != len(substitute_ids):
            raise HTTPException(status_code=422, detail="A Recipe ingredient cannot list the same substitute more than once")
        if item.ingredient_id in substitute_ids:
            raise HTTPException(status_code=422, detail="An ingredient cannot substitute for itself")
        if sum(1 for sub in item.substitutions if sub.preferred) > 1:
            raise HTTPException(status_code=422, detail="Only one preferred substitution is allowed per Recipe ingredient")
        if substitute_ids:
            substitutes = list(db.scalars(select(Ingredient).where(Ingredient.id.in_(substitute_ids), Ingredient.household_id == DEFAULT_HOUSEHOLD_ID, Ingredient.active.is_(True))))
            if len(substitutes) != len(substitute_ids):
                raise HTTPException(status_code=400, detail="One or more substitute ingredients were not found or are archived")
    for item in payload.advance_prep:
        if item.prep_group_key and item.prep_group_key not in known_group_keys:
            raise HTTPException(status_code=422, detail=f"Unknown prep group key {item.prep_group_key}")
    equipment_ids = [item.equipment_id for item in payload.equipment]
    if len(set(equipment_ids)) != len(equipment_ids):
        raise HTTPException(status_code=422, detail="A Recipe cannot list the same Equipment more than once")
    if equipment_ids:
        available = list(db.scalars(select(Equipment).where(Equipment.id.in_(equipment_ids), Equipment.household_id == DEFAULT_HOUSEHOLD_ID, Equipment.active.is_(True))))
        if len(available) != len(equipment_ids):
            raise HTTPException(status_code=400, detail="One or more Equipment items were not found or are archived")
    unique_tag_ids = list(dict.fromkeys(payload.tag_ids)); tags: list[Tag] = []
    if unique_tag_ids:
        tags = list(db.scalars(select(Tag).where(Tag.id.in_(unique_tag_ids), Tag.household_id == DEFAULT_HOUSEHOLD_ID, Tag.active.is_(True))))
        if len(tags) != len(unique_tag_ids):
            raise HTTPException(status_code=400, detail="One or more tags were not found")
    meal_types = sorted({value.strip().upper() for value in payload.meal_types if value.strip()})
    return tags, meal_types


def _snapshot_variant_overrides(recipe: Recipe) -> list[tuple[RecipeVariant, list[dict]]]:
    ingredient_by_id = {item.id: item for item in recipe.ingredients}; result: list[tuple[RecipeVariant, list[dict]]] = []
    for variant in recipe.variants:
        rows = []
        for override in variant.overrides:
            old_item = ingredient_by_id.get(override.recipe_ingredient_id)
            if old_item is None: continue
            selected_sub = next((sub for sub in old_item.substitutions if sub.id == override.substitution_id), None)
            rows.append({"canonical_ingredient_id": old_item.ingredient_id, "quantity": override.quantity, "unit_id": override.unit_id, "substitute_ingredient_id": selected_sub.substitute_ingredient_id if selected_sub else None, "preparation": override.preparation, "prep_method": override.prep_method, "prep_size": override.prep_size, "prep_state": override.prep_state, "notes": override.notes})
        result.append((variant, rows))
    return result


def _save_recipe(db: Session, recipe: Recipe, payload: RecipeCreate | RecipeUpdate) -> Recipe:
    normalized_name = normalize_name(payload.name)
    if not normalized_name: raise HTTPException(status_code=422, detail="Recipe name cannot be blank")
    existing = select(Recipe.id).where(Recipe.household_id == DEFAULT_HOUSEHOLD_ID, Recipe.normalized_name == normalized_name)
    if recipe.id is not None: existing = existing.where(Recipe.id != recipe.id)
    if db.scalar(existing) is not None: raise HTTPException(status_code=409, detail="Recipe name already exists")
    tags, meal_types = _validate_recipe_references(db, payload)
    preserved_variants = _snapshot_variant_overrides(recipe) if recipe.id is not None else []
    preserved_type_title = {item.title: item.task_type for item in recipe.advance_prep} if recipe.id is not None else {}
    preserved_type_order = {item.sort_order: item.task_type for item in recipe.advance_prep} if recipe.id is not None else {}
    preserved_reminder_title = {item.title: (item.reminder_enabled, item.reminder_offset_minutes) for item in recipe.advance_prep} if recipe.id is not None else {}
    preserved_reminder_order = {item.sort_order: (item.reminder_enabled, item.reminder_offset_minutes) for item in recipe.advance_prep} if recipe.id is not None else {}

    recipe.name = payload.name.strip(); recipe.normalized_name = normalized_name
    recipe.description = payload.description.strip() if payload.description else None
    recipe.base_servings = payload.base_servings; recipe.serving_unit = payload.serving_unit.strip()
    recipe.yield_quantity = payload.yield_quantity; recipe.yield_unit_id = payload.yield_unit_id
    recipe.prep_time_minutes = payload.prep_time_minutes; recipe.cook_time_minutes = payload.cook_time_minutes
    recipe.notes = payload.notes.strip() if payload.notes else None; recipe.favorite = payload.favorite
    if isinstance(payload, RecipeUpdate): recipe.active = payload.active
    db.add(recipe)
    for variant, _rows in preserved_variants: variant.overrides.clear()
    recipe.ingredients.clear(); recipe.advance_prep.clear(); recipe.equipment.clear(); recipe.prep_groups.clear(); recipe.meal_types.clear(); recipe.tags = []; db.flush()

    group_ids: dict[str, int] = {}
    for group in sorted(payload.prep_groups, key=lambda value: value.sort_order):
        model = RecipePrepGroup(name=group.name.strip(), sort_order=group.sort_order); recipe.prep_groups.append(model); db.flush(); group_ids[group.client_key] = model.id
    for item in sorted(payload.advance_prep, key=lambda value: value.sort_order):
        explicit_type = "task_type" in item.model_fields_set
        task_type = item.task_type if explicit_type else preserved_type_title.get(item.title.strip(), preserved_type_order.get(item.sort_order, "PREP"))
        explicit_reminder = "reminder_enabled" in item.model_fields_set or "reminder_offset_minutes" in item.model_fields_set
        reminder_enabled, reminder_offset = (item.reminder_enabled, item.reminder_offset_minutes) if explicit_reminder else preserved_reminder_title.get(item.title.strip(), preserved_reminder_order.get(item.sort_order, (False, None)))
        if reminder_enabled and reminder_offset is None: reminder_offset = 15
        recipe.advance_prep.append(RecipeAdvancePrep(prep_group_id=group_ids.get(item.prep_group_key) if item.prep_group_key else None, task_type=task_type, title=item.title.strip(), lead_time_minutes=item.lead_time_minutes, duration_minutes=item.duration_minutes, instructions=item.instructions.strip() if item.instructions else None, reminder_enabled=reminder_enabled, reminder_offset_minutes=reminder_offset, sort_order=item.sort_order))
    for item in sorted(payload.equipment, key=lambda value: value.sort_order): recipe.equipment.append(RecipeEquipment(equipment_id=item.equipment_id, quantity=item.quantity, notes=item.notes.strip() if item.notes else None, sort_order=item.sort_order))

    new_by_canonical: dict[int, RecipeIngredient] = {}
    for item in sorted(payload.ingredients, key=lambda value: value.sort_order):
        model = RecipeIngredient(ingredient_id=item.ingredient_id, prep_group_id=group_ids.get(item.prep_group_key) if item.prep_group_key else None, quantity=item.quantity, unit_id=item.unit_id, display_text=item.display_text.strip() if item.display_text else None, preparation=item.preparation.strip() if item.preparation else None, prep_method=item.prep_method.strip() if item.prep_method else None, prep_size=item.prep_size.strip() if item.prep_size else None, prep_state=item.prep_state.strip() if item.prep_state else None, optional=item.optional, scaling_mode=item.scaling_mode.upper(), required_state=item.required_state.strip().upper(), sort_order=item.sort_order, notes=item.notes.strip() if item.notes else None)
        recipe.ingredients.append(model); db.flush(); new_by_canonical.setdefault(item.ingredient_id, model)
        for sub in sorted(item.substitutions, key=lambda value: value.sort_order): model.substitutions.append(RecipeIngredientSubstitution(substitute_ingredient_id=sub.substitute_ingredient_id, ratio=sub.ratio, preferred=sub.preferred, notes=sub.notes.strip() if sub.notes else None, sort_order=sub.sort_order))
        db.flush()
    for variant, rows in preserved_variants:
        for row in rows:
            new_item = new_by_canonical.get(row["canonical_ingredient_id"])
            if new_item is None: continue
            sub_id = None
            if row["substitute_ingredient_id"] is not None:
                match = next((sub for sub in new_item.substitutions if sub.substitute_ingredient_id == row["substitute_ingredient_id"]), None); sub_id = match.id if match else None
            variant.overrides.append(RecipeVariantIngredientOverride(recipe_ingredient_id=new_item.id, quantity=row["quantity"], unit_id=row["unit_id"], substitution_id=sub_id, preparation=row["preparation"], prep_method=row["prep_method"], prep_size=row["prep_size"], prep_state=row["prep_state"], notes=row["notes"]))
    for meal_type in meal_types: recipe.meal_types.append(RecipeMealType(meal_type=meal_type))
    recipe.tags = tags
    try: db.commit()
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Recipe could not be saved") from exc
    return _recipe_or_404(db, recipe.id)


@router.get("", response_model=list[RecipeRead])
def list_recipes(search: str | None = Query(default=None, max_length=160), meal_type: str | None = Query(default=None, max_length=30), tag_id: int | None = None, favorite: bool | None = None, include_inactive: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    statement = _recipe_statement().where(Recipe.household_id == DEFAULT_HOUSEHOLD_ID)
    if not include_inactive: statement = statement.where(Recipe.active.is_(True))
    if search and normalize_name(search): statement = statement.where(Recipe.normalized_name.like(f"%{normalize_name(search)}%"))
    if meal_type and meal_type.strip(): statement = statement.where(Recipe.meal_types.any(RecipeMealType.meal_type == meal_type.strip().upper()))
    if tag_id is not None: statement = statement.where(Recipe.tags.any(Tag.id == tag_id))
    if favorite is not None: statement = statement.where(Recipe.favorite.is_(favorite))
    return [_recipe_payload(recipe) for recipe in db.scalars(statement.order_by(Recipe.name)).unique()]


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> dict: return _recipe_payload(_recipe_or_404(db, recipe_id))

@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)) -> dict:
    recipe = Recipe(household_id=DEFAULT_HOUSEHOLD_ID, name=payload.name.strip(), normalized_name=normalize_name(payload.name), base_servings=payload.base_servings)
    return _recipe_payload(_save_recipe(db, recipe, payload))

@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: Session = Depends(get_db)) -> dict: return _recipe_payload(_save_recipe(db, _recipe_or_404(db, recipe_id), payload))

@router.put("/{recipe_id}/advance-prep/{prep_id}/type", response_model=RecipeRead)
def update_advance_prep_type(recipe_id: int, prep_id: int, task_type: str = Query(...), db: Session = Depends(get_db)) -> dict:
    normalized = task_type.strip().upper()
    if normalized not in VALID_PREP_TASK_TYPES: raise HTTPException(status_code=422, detail="task_type must be PREP, THAW, MARINATE, SOAK, or PROOF")
    recipe = _recipe_or_404(db, recipe_id); prep = next((item for item in recipe.advance_prep if item.id == prep_id), None)
    if prep is None: raise HTTPException(status_code=404, detail="Advance prep task not found")
    prep.task_type = normalized; db.commit(); return _recipe_payload(_recipe_or_404(db, recipe_id))

@router.put("/{recipe_id}/advance-prep/{prep_id}/reminder", response_model=RecipeRead)
def update_advance_prep_reminder(recipe_id: int, prep_id: int, enabled: bool = Query(...), offset_minutes: int | None = Query(default=None, ge=0), db: Session = Depends(get_db)) -> dict:
    recipe = _recipe_or_404(db, recipe_id); prep = next((item for item in recipe.advance_prep if item.id == prep_id), None)
    if prep is None: raise HTTPException(status_code=404, detail="Advance prep task not found")
    prep.reminder_enabled = enabled
    prep.reminder_offset_minutes = (15 if offset_minutes is None else offset_minutes) if enabled else None
    db.commit(); return _recipe_payload(_recipe_or_404(db, recipe_id))

@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = _recipe_or_404(db, recipe_id); recipe.active = False; db.commit()


@router.post("/{recipe_id}/scale", response_model=RecipeScaleResponse)
def scale_recipe(recipe_id: int, payload: RecipeScaleRequest, db: Session = Depends(get_db)) -> dict:
    recipe = _recipe_or_404(db, recipe_id); variant = None
    if payload.variant_id is not None:
        variant = next((value for value in recipe.variants if value.id == payload.variant_id and value.active), None)
        if variant is None: raise HTTPException(status_code=400, detail="Recipe variant not found or inactive")
    variant_overrides = {row.recipe_ingredient_id: row for row in variant.overrides} if variant else {}; scale_factor = Decimal(payload.requested_servings) / Decimal(recipe.base_servings); scaled_items: list[dict] = []
    for item in recipe.ingredients:
        variant_override = variant_overrides.get(item.id); source_quantity = Decimal(variant_override.quantity) if variant_override and variant_override.quantity is not None else Decimal(item.quantity); source_unit_id = variant_override.unit_id if variant_override and variant_override.unit_id is not None else item.unit_id; source_unit = db.get(MeasurementUnit, source_unit_id)
        if source_unit is None: raise HTTPException(status_code=409, detail=f"Stored unit {source_unit_id} no longer exists")
        scaled_quantity, manual_review = scale_quantity(source_quantity, scale_factor, item.scaling_mode); selected_substitution = None; requested_sub_id = payload.substitution_overrides.get(item.id)
        if requested_sub_id is not None:
            selected_substitution = next((sub for sub in item.substitutions if sub.id == requested_sub_id), None)
            if selected_substitution is None: raise HTTPException(status_code=400, detail=f"Substitution {requested_sub_id} is not valid for Recipe ingredient {item.id}")
        elif variant_override and variant_override.substitution_id is not None: selected_substitution = next((sub for sub in item.substitutions if sub.id == variant_override.substitution_id), None)
        else: selected_substitution = next((sub for sub in item.substitutions if sub.preferred), None)
        output_ingredient_id = item.ingredient_id; substitution_id = None
        if selected_substitution is not None: scaled_quantity *= Decimal(selected_substitution.ratio); output_ingredient_id = selected_substitution.substitute_ingredient_id; substitution_id = selected_substitution.id
        target_unit = source_unit; requested_unit_code = payload.unit_overrides.get(item.id)
        if requested_unit_code:
            target_unit = db.scalar(select(MeasurementUnit).where(MeasurementUnit.code == requested_unit_code))
            if target_unit is None: raise HTTPException(status_code=400, detail=f"Measurement unit {requested_unit_code} not found")
            try: scaled_quantity = convert_quantity(scaled_quantity, source_unit, target_unit)
            except UnitConversionError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
        scaled_items.append({"recipe_ingredient_id": item.id, "ingredient_id": output_ingredient_id, "canonical_ingredient_id": item.ingredient_id, "substitution_id": substitution_id, "prep_group_id": item.prep_group_id, "quantity": scaled_quantity, "unit_id": target_unit.id, "unit_code": target_unit.code, "scaling_mode": item.scaling_mode, "manual_review": manual_review, "preparation": variant_override.preparation if variant_override and variant_override.preparation is not None else item.preparation, "prep_method": variant_override.prep_method if variant_override and variant_override.prep_method is not None else item.prep_method, "prep_size": variant_override.prep_size if variant_override and variant_override.prep_size is not None else item.prep_size, "prep_state": variant_override.prep_state if variant_override and variant_override.prep_state is not None else item.prep_state})
    return {"recipe_id": recipe.id, "base_servings": recipe.base_servings, "requested_servings": payload.requested_servings, "scale_factor": scale_factor, "variant_id": variant.id if variant else None, "ingredients": scaled_items}
