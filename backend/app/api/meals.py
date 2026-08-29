from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Tag
from app.models.meal import Meal, MealMealType, MealRecipe
from app.models.recipe import Recipe
from app.schemas.meal import MealCreate, MealRead, MealUpdate
from app.services.normalization import normalize_name

router = APIRouter(prefix="/api/meals", tags=["meals"])
DEFAULT_HOUSEHOLD_ID = 1


def _statement():
    return select(Meal).options(
        selectinload(Meal.recipes),
        selectinload(Meal.meal_types),
        selectinload(Meal.tags),
    )


def _meal_or_404(db: Session, meal_id: int) -> Meal:
    meal = db.scalar(_statement().where(Meal.id == meal_id, Meal.household_id == DEFAULT_HOUSEHOLD_ID))
    if meal is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return meal


def _payload(meal: Meal) -> dict:
    return {
        "id": meal.id,
        "household_id": meal.household_id,
        "name": meal.name,
        "description": meal.description,
        "favorite": meal.favorite,
        "active": meal.active,
        "meal_types": [item.meal_type for item in meal.meal_types],
        "tags": meal.tags,
        "recipes": meal.recipes,
    }


def _validate_refs(db: Session, payload: MealCreate | MealUpdate) -> list[Tag]:
    for component in payload.recipes:
        recipe = db.get(Recipe, component.recipe_id)
        if recipe is None or recipe.household_id != DEFAULT_HOUSEHOLD_ID or not recipe.active:
            raise HTTPException(status_code=400, detail=f"Recipe {component.recipe_id} not found")

    if not payload.tag_ids:
        return []

    tags = list(db.scalars(select(Tag).where(Tag.id.in_(set(payload.tag_ids)))))
    if len(tags) != len(set(payload.tag_ids)) or any(
        tag.household_id != DEFAULT_HOUSEHOLD_ID or not tag.active for tag in tags
    ):
        raise HTTPException(status_code=400, detail="One or more tags not found")
    return tags


def _normalize_meal_types(values: list[str]) -> list[str]:
    return sorted({value.strip().upper() for value in values if value.strip()})


def _save(db: Session, meal: Meal, payload: MealCreate | MealUpdate) -> Meal:
    tags = _validate_refs(db, payload)
    meal.name = payload.name.strip()
    meal.normalized_name = normalize_name(payload.name)
    meal.description = payload.description.strip() if payload.description else None
    meal.favorite = payload.favorite
    if isinstance(payload, MealUpdate):
        meal.active = payload.active

    db.add(meal)
    meal.recipes.clear()
    meal.meal_types.clear()
    meal.tags.clear()
    db.flush()

    for component in sorted(payload.recipes, key=lambda item: item.sort_order):
        meal.recipes.append(
            MealRecipe(
                recipe_id=component.recipe_id,
                serving_multiplier=component.serving_multiplier,
                default_servings=component.default_servings,
                sort_order=component.sort_order,
                notes=component.notes.strip() if component.notes else None,
            )
        )
    for meal_type in _normalize_meal_types(payload.meal_types):
        meal.meal_types.append(MealMealType(meal_type=meal_type))
    meal.tags.extend(tags)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meal name already exists") from exc
    return _meal_or_404(db, meal.id)


@router.get("", response_model=list[MealRead])
def list_meals(
    search: str | None = Query(default=None, max_length=160),
    meal_type: str | None = Query(default=None, max_length=30),
    tag_id: int | None = None,
    favorite: bool | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    statement = _statement().where(Meal.household_id == DEFAULT_HOUSEHOLD_ID)
    if not include_inactive:
        statement = statement.where(Meal.active.is_(True))
    if search and normalize_name(search):
        statement = statement.where(Meal.normalized_name.like(f"%{normalize_name(search)}%"))
    if meal_type and meal_type.strip():
        statement = statement.where(Meal.meal_types.any(MealMealType.meal_type == meal_type.strip().upper()))
    if tag_id is not None:
        statement = statement.where(Meal.tags.any(Tag.id == tag_id))
    if favorite is not None:
        statement = statement.where(Meal.favorite.is_(favorite))
    meals = list(db.scalars(statement.order_by(Meal.name)).unique())
    return [_payload(meal) for meal in meals]


@router.get("/{meal_id}", response_model=MealRead)
def get_meal(meal_id: int, db: Session = Depends(get_db)) -> dict:
    return _payload(_meal_or_404(db, meal_id))


@router.post("", response_model=MealRead, status_code=status.HTTP_201_CREATED)
def create_meal(payload: MealCreate, db: Session = Depends(get_db)) -> dict:
    meal = Meal(
        household_id=DEFAULT_HOUSEHOLD_ID,
        name=payload.name.strip(),
        normalized_name=normalize_name(payload.name),
    )
    return _payload(_save(db, meal, payload))


@router.put("/{meal_id}", response_model=MealRead)
def update_meal(meal_id: int, payload: MealUpdate, db: Session = Depends(get_db)) -> dict:
    return _payload(_save(db, _meal_or_404(db, meal_id), payload))


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_meal(meal_id: int, db: Session = Depends(get_db)) -> None:
    meal = _meal_or_404(db, meal_id)
    meal.active = False
    db.commit()
