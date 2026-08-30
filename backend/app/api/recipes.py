from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.engines.recipe_scaling import scale_quantity
from app.models.equipment import Equipment
from app.models.ingredient import Ingredient, Tag
from app.models.recipe import Recipe, RecipeAdvancePrep, RecipeEquipment, RecipeIngredient, RecipeMealType, RecipePrepGroup
from app.models.reference import MeasurementUnit
from app.schemas.recipe import RecipeCreate, RecipeRead, RecipeScaleRequest, RecipeScaleResponse, RecipeUpdate
from app.services.normalization import normalize_name
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/recipes", tags=["recipes"])
DEFAULT_HOUSEHOLD_ID = 1


def _recipe_statement():
    return select(Recipe).options(
        selectinload(Recipe.prep_groups),
        selectinload(Recipe.advance_prep),
        selectinload(Recipe.equipment),
        selectinload(Recipe.ingredients),
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
        "id": recipe.id,
        "household_id": recipe.household_id,
        "name": recipe.name,
        "description": recipe.description,
        "base_servings": recipe.base_servings,
        "serving_unit": recipe.serving_unit,
        "yield_quantity": recipe.yield_quantity,
        "yield_unit_id": recipe.yield_unit_id,
        "prep_time_minutes": recipe.prep_time_minutes,
        "cook_time_minutes": recipe.cook_time_minutes,
        "notes": recipe.notes,
        "favorite": recipe.favorite,
        "active": recipe.active,
        "meal_types": [item.meal_type for item in recipe.meal_types],
        "tags": recipe.tags,
        "prep_groups": recipe.prep_groups,
        "advance_prep": recipe.advance_prep,
        "equipment": recipe.equipment,
        "ingredients": recipe.ingredients,
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

    unique_tag_ids = list(dict.fromkeys(payload.tag_ids))
    tags: list[Tag] = []
    if unique_tag_ids:
        tags = list(db.scalars(select(Tag).where(Tag.id.in_(unique_tag_ids), Tag.household_id == DEFAULT_HOUSEHOLD_ID, Tag.active.is_(True))))
        if len(tags) != len(unique_tag_ids):
            raise HTTPException(status_code=400, detail="One or more tags were not found")

    meal_types = sorted({value.strip().upper() for value in payload.meal_types if value.strip()})
    return tags, meal_types


def _save_recipe(db: Session, recipe: Recipe, payload: RecipeCreate | RecipeUpdate) -> Recipe:
    normalized_name = normalize_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Recipe name cannot be blank")

    existing = select(Recipe.id).where(Recipe.household_id == DEFAULT_HOUSEHOLD_ID, Recipe.normalized_name == normalized_name)
    if recipe.id is not None:
        existing = existing.where(Recipe.id != recipe.id)
    if db.scalar(existing) is not None:
        raise HTTPException(status_code=409, detail="Recipe name already exists")

    tags, meal_types = _validate_recipe_references(db, payload)

    recipe.name = payload.name.strip()
    recipe.normalized_name = normalized_name
    recipe.description = payload.description.strip() if payload.description else None
    recipe.base_servings = payload.base_servings
    recipe.serving_unit = payload.serving_unit.strip()
    recipe.yield_quantity = payload.yield_quantity
    recipe.yield_unit_id = payload.yield_unit_id
    recipe.prep_time_minutes = payload.prep_time_minutes
    recipe.cook_time_minutes = payload.cook_time_minutes
    recipe.notes = payload.notes.strip() if payload.notes else None
    recipe.favorite = payload.favorite
    if isinstance(payload, RecipeUpdate):
        recipe.active = payload.active

    db.add(recipe)
    recipe.ingredients.clear()
    recipe.advance_prep.clear()
    recipe.equipment.clear()
    recipe.prep_groups.clear()
    recipe.meal_types.clear()
    recipe.tags = []
    db.flush()

    group_ids: dict[str, int] = {}
    for group in sorted(payload.prep_groups, key=lambda value: value.sort_order):
        model = RecipePrepGroup(name=group.name.strip(), sort_order=group.sort_order)
        recipe.prep_groups.append(model)
        db.flush()
        group_ids[group.client_key] = model.id

    for item in sorted(payload.advance_prep, key=lambda value: value.sort_order):
        recipe.advance_prep.append(
            RecipeAdvancePrep(
                prep_group_id=group_ids.get(item.prep_group_key) if item.prep_group_key else None,
                title=item.title.strip(),
                lead_time_minutes=item.lead_time_minutes,
                duration_minutes=item.duration_minutes,
                instructions=item.instructions.strip() if item.instructions else None,
                sort_order=item.sort_order,
            )
        )

    for item in sorted(payload.equipment, key=lambda value: value.sort_order):
        recipe.equipment.append(
            RecipeEquipment(
                equipment_id=item.equipment_id,
                quantity=item.quantity,
                notes=item.notes.strip() if item.notes else None,
                sort_order=item.sort_order,
            )
        )

    for item in payload.ingredients:
        recipe.ingredients.append(
            RecipeIngredient(
                ingredient_id=item.ingredient_id,
                prep_group_id=group_ids.get(item.prep_group_key) if item.prep_group_key else None,
                quantity=item.quantity,
                unit_id=item.unit_id,
                display_text=item.display_text.strip() if item.display_text else None,
                preparation=item.preparation.strip() if item.preparation else None,
                prep_method=item.prep_method.strip() if item.prep_method else None,
                prep_size=item.prep_size.strip() if item.prep_size else None,
                prep_state=item.prep_state.strip() if item.prep_state else None,
                optional=item.optional,
                scaling_mode=item.scaling_mode.upper(),
                required_state=item.required_state.strip().upper(),
                sort_order=item.sort_order,
                notes=item.notes.strip() if item.notes else None,
            )
        )
    for meal_type in meal_types:
        recipe.meal_types.append(RecipeMealType(meal_type=meal_type))
    recipe.tags = tags

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Recipe could not be saved") from exc
    return _recipe_or_404(db, recipe.id)


@router.get("", response_model=list[RecipeRead])
def list_recipes(search: str | None = Query(default=None, max_length=160), meal_type: str | None = Query(default=None, max_length=30), tag_id: int | None = None, favorite: bool | None = None, include_inactive: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    statement = _recipe_statement().where(Recipe.household_id == DEFAULT_HOUSEHOLD_ID)
    if not include_inactive:
        statement = statement.where(Recipe.active.is_(True))
    if search and normalize_name(search):
        statement = statement.where(Recipe.normalized_name.like(f"%{normalize_name(search)}%"))
    if meal_type and meal_type.strip():
        statement = statement.where(Recipe.meal_types.any(RecipeMealType.meal_type == meal_type.strip().upper()))
    if tag_id is not None:
        statement = statement.where(Recipe.tags.any(Tag.id == tag_id))
    if favorite is not None:
        statement = statement.where(Recipe.favorite.is_(favorite))
    recipes = list(db.scalars(statement.order_by(Recipe.name)).unique())
    return [_recipe_payload(recipe) for recipe in recipes]


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> dict:
    return _recipe_payload(_recipe_or_404(db, recipe_id))


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)) -> dict:
    recipe = Recipe(household_id=DEFAULT_HOUSEHOLD_ID, name=payload.name.strip(), normalized_name=normalize_name(payload.name), base_servings=payload.base_servings)
    return _recipe_payload(_save_recipe(db, recipe, payload))


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: Session = Depends(get_db)) -> dict:
    return _recipe_payload(_save_recipe(db, _recipe_or_404(db, recipe_id), payload))


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = _recipe_or_404(db, recipe_id)
    recipe.active = False
    db.commit()


@router.post("/{recipe_id}/scale", response_model=RecipeScaleResponse)
def scale_recipe(recipe_id: int, payload: RecipeScaleRequest, db: Session = Depends(get_db)) -> dict:
    recipe = _recipe_or_404(db, recipe_id)
    scale_factor = Decimal(payload.requested_servings) / Decimal(recipe.base_servings)
    scaled_items: list[dict] = []

    for item in recipe.ingredients:
        source_unit = db.get(MeasurementUnit, item.unit_id)
        if source_unit is None:
            raise HTTPException(status_code=409, detail=f"Stored unit {item.unit_id} no longer exists")
        scaled_quantity, manual_review = scale_quantity(Decimal(item.quantity), scale_factor, item.scaling_mode)
        target_unit = source_unit
        requested_unit_code = payload.unit_overrides.get(item.id)
        if requested_unit_code:
            target_unit = db.scalar(select(MeasurementUnit).where(MeasurementUnit.code == requested_unit_code))
            if target_unit is None:
                raise HTTPException(status_code=400, detail=f"Measurement unit {requested_unit_code} not found")
            try:
                scaled_quantity = convert_quantity(scaled_quantity, source_unit, target_unit)
            except UnitConversionError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        scaled_items.append({
            "recipe_ingredient_id": item.id,
            "ingredient_id": item.ingredient_id,
            "prep_group_id": item.prep_group_id,
            "quantity": scaled_quantity,
            "unit_id": target_unit.id,
            "unit_code": target_unit.code,
            "scaling_mode": item.scaling_mode,
            "manual_review": manual_review,
            "preparation": item.preparation,
            "prep_method": item.prep_method,
            "prep_size": item.prep_size,
            "prep_state": item.prep_state,
        })

    return {"recipe_id": recipe.id, "base_servings": recipe.base_servings, "requested_servings": payload.requested_servings, "scale_factor": scale_factor, "ingredients": scaled_items}
