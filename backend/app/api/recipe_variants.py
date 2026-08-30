from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.recipe import Recipe, RecipeIngredient, RecipeIngredientSubstitution, RecipeVariant, RecipeVariantIngredientOverride
from app.models.reference import MeasurementUnit
from app.schemas.recipe import RecipeVariantInput, RecipeVariantRead
from app.services.normalization import normalize_name

router = APIRouter(prefix="/api/recipes", tags=["recipe-variants"])
HOUSEHOLD_ID = 1


def _recipe(db: Session, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.household_id != HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _variant_statement():
    return select(RecipeVariant).options(selectinload(RecipeVariant.overrides))


def _variant(db: Session, recipe_id: int, variant_id: int) -> RecipeVariant:
    variant = db.scalar(_variant_statement().where(RecipeVariant.id == variant_id, RecipeVariant.recipe_id == recipe_id))
    if variant is None:
        raise HTTPException(status_code=404, detail="Recipe variant not found")
    return variant


def _validate_overrides(db: Session, recipe_id: int, payload: RecipeVariantInput) -> None:
    ingredient_ids = [item.recipe_ingredient_id for item in payload.overrides]
    if len(set(ingredient_ids)) != len(ingredient_ids):
        raise HTTPException(status_code=422, detail="A variant cannot override the same Recipe ingredient more than once")
    if not ingredient_ids:
        return
    recipe_ingredients = {
        item.id: item
        for item in db.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.id.in_(ingredient_ids), RecipeIngredient.recipe_id == recipe_id)
            .options(selectinload(RecipeIngredient.substitutions))
        )
    }
    if len(recipe_ingredients) != len(ingredient_ids):
        raise HTTPException(status_code=422, detail="One or more variant overrides reference ingredients outside this Recipe")

    for override in payload.overrides:
        if override.unit_id is not None and db.get(MeasurementUnit, override.unit_id) is None:
            raise HTTPException(status_code=400, detail=f"Measurement unit {override.unit_id} not found")
        if override.substitution_id is not None:
            allowed = {sub.id for sub in recipe_ingredients[override.recipe_ingredient_id].substitutions}
            if override.substitution_id not in allowed:
                raise HTTPException(status_code=422, detail="Variant substitution must be one of the Recipe ingredient's saved substitutions")


def _save(db: Session, recipe_id: int, variant: RecipeVariant, payload: RecipeVariantInput) -> RecipeVariant:
    _recipe(db, recipe_id)
    normalized = normalize_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Variant name cannot be blank")
    existing = select(RecipeVariant.id).where(RecipeVariant.recipe_id == recipe_id, RecipeVariant.normalized_name == normalized)
    if variant.id is not None:
        existing = existing.where(RecipeVariant.id != variant.id)
    if db.scalar(existing) is not None:
        raise HTTPException(status_code=409, detail="Variant name already exists for this Recipe")
    _validate_overrides(db, recipe_id, payload)

    variant.recipe_id = recipe_id
    variant.name = payload.name.strip()
    variant.normalized_name = normalized
    variant.notes = payload.notes.strip() if payload.notes else None
    variant.active = payload.active
    variant.sort_order = payload.sort_order
    db.add(variant)
    variant.overrides.clear()
    db.flush()
    for override in payload.overrides:
        variant.overrides.append(
            RecipeVariantIngredientOverride(
                recipe_ingredient_id=override.recipe_ingredient_id,
                quantity=override.quantity,
                unit_id=override.unit_id,
                substitution_id=override.substitution_id,
                preparation=override.preparation.strip() if override.preparation else None,
                prep_method=override.prep_method.strip() if override.prep_method else None,
                prep_size=override.prep_size.strip() if override.prep_size else None,
                prep_state=override.prep_state.strip() if override.prep_state else None,
                notes=override.notes.strip() if override.notes else None,
            )
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Recipe variant could not be saved") from exc
    return _variant(db, recipe_id, variant.id)


@router.get("/{recipe_id}/variants", response_model=list[RecipeVariantRead])
def list_variants(recipe_id: int, include_inactive: bool = False, db: Session = Depends(get_db)) -> list[RecipeVariant]:
    _recipe(db, recipe_id)
    statement = _variant_statement().where(RecipeVariant.recipe_id == recipe_id)
    if not include_inactive:
        statement = statement.where(RecipeVariant.active.is_(True))
    return list(db.scalars(statement.order_by(RecipeVariant.sort_order, RecipeVariant.name)).unique())


@router.post("/{recipe_id}/variants", response_model=RecipeVariantRead, status_code=status.HTTP_201_CREATED)
def create_variant(recipe_id: int, payload: RecipeVariantInput, db: Session = Depends(get_db)) -> RecipeVariant:
    return _save(db, recipe_id, RecipeVariant(recipe_id=recipe_id, name=payload.name, normalized_name=normalize_name(payload.name)), payload)


@router.put("/{recipe_id}/variants/{variant_id}", response_model=RecipeVariantRead)
def update_variant(recipe_id: int, variant_id: int, payload: RecipeVariantInput, db: Session = Depends(get_db)) -> RecipeVariant:
    return _save(db, recipe_id, _variant(db, recipe_id, variant_id), payload)


@router.delete("/{recipe_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_variant(recipe_id: int, variant_id: int, db: Session = Depends(get_db)) -> None:
    variant = _variant(db, recipe_id, variant_id)
    variant.active = False
    db.commit()
