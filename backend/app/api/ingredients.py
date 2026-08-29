from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient, IngredientAlias, Tag
from app.models.reference import InventoryLocation, MeasurementUnit, ShoppingCategory
from app.schemas.ingredient import IngredientCreate, IngredientRead, IngredientUpdate, TagCreate, TagRead, TagUpdate
from app.services.normalization import normalize_name

router = APIRouter(prefix="/api", tags=["ingredients"])
DEFAULT_HOUSEHOLD_ID = 1


def _ingredient_or_404(db: Session, ingredient_id: int) -> Ingredient:
    ingredient = db.scalar(
        select(Ingredient)
        .options(selectinload(Ingredient.aliases))
        .where(Ingredient.id == ingredient_id, Ingredient.household_id == DEFAULT_HOUSEHOLD_ID)
    )
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ingredient


def _validate_ingredient_references(db: Session, payload: IngredientCreate | IngredientUpdate) -> None:
    if payload.shopping_category_id is not None:
        category = db.get(ShoppingCategory, payload.shopping_category_id)
        if category is None or category.household_id != DEFAULT_HOUSEHOLD_ID or not category.active:
            raise HTTPException(status_code=400, detail="Shopping category not found")
    if payload.preferred_unit_id is not None and db.get(MeasurementUnit, payload.preferred_unit_id) is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    if payload.default_location_id is not None:
        location = db.get(InventoryLocation, payload.default_location_id)
        if location is None or location.household_id != DEFAULT_HOUSEHOLD_ID or not location.active:
            raise HTTPException(status_code=400, detail="Inventory location not found")


def _normalized_aliases(values: list[str], ingredient_name: str) -> list[tuple[str, str]]:
    normalized_name = normalize_name(ingredient_name)
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for value in values:
        alias = value.strip()
        normalized = normalize_name(alias)
        if not normalized or normalized == normalized_name or normalized in seen:
            continue
        seen.add(normalized)
        result.append((alias, normalized))
    return result


def _validate_ingredient_identity(
    db: Session,
    normalized_name: str,
    aliases: list[tuple[str, str]],
    ingredient_id: int | None,
) -> None:
    other_ingredient = select(Ingredient.id).where(
        Ingredient.household_id == DEFAULT_HOUSEHOLD_ID,
        Ingredient.normalized_name == normalized_name,
    )
    if ingredient_id is not None:
        other_ingredient = other_ingredient.where(Ingredient.id != ingredient_id)
    if db.scalar(other_ingredient) is not None:
        raise HTTPException(status_code=409, detail="Ingredient name already exists")

    name_alias_conflict = (
        select(IngredientAlias.id)
        .join(Ingredient, Ingredient.id == IngredientAlias.ingredient_id)
        .where(
            Ingredient.household_id == DEFAULT_HOUSEHOLD_ID,
            IngredientAlias.normalized_alias == normalized_name,
        )
    )
    if ingredient_id is not None:
        name_alias_conflict = name_alias_conflict.where(IngredientAlias.ingredient_id != ingredient_id)
    if db.scalar(name_alias_conflict) is not None:
        raise HTTPException(status_code=409, detail="Ingredient name conflicts with an existing alias")

    for _, normalized_alias in aliases:
        canonical_conflict = select(Ingredient.id).where(
            Ingredient.household_id == DEFAULT_HOUSEHOLD_ID,
            Ingredient.normalized_name == normalized_alias,
        )
        if ingredient_id is not None:
            canonical_conflict = canonical_conflict.where(Ingredient.id != ingredient_id)
        if db.scalar(canonical_conflict) is not None:
            raise HTTPException(status_code=409, detail="Ingredient alias conflicts with an existing ingredient")

        alias_conflict = (
            select(IngredientAlias.id)
            .join(Ingredient, Ingredient.id == IngredientAlias.ingredient_id)
            .where(
                Ingredient.household_id == DEFAULT_HOUSEHOLD_ID,
                IngredientAlias.normalized_alias == normalized_alias,
            )
        )
        if ingredient_id is not None:
            alias_conflict = alias_conflict.where(IngredientAlias.ingredient_id != ingredient_id)
        if db.scalar(alias_conflict) is not None:
            raise HTTPException(status_code=409, detail="Ingredient alias already exists")


def _save_ingredient(db: Session, ingredient: Ingredient, payload: IngredientCreate | IngredientUpdate) -> Ingredient:
    _validate_ingredient_references(db, payload)
    normalized_name = normalize_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Ingredient name cannot be blank")
    aliases = _normalized_aliases(payload.aliases, payload.name)
    _validate_ingredient_identity(db, normalized_name, aliases, ingredient.id if ingredient.id else None)

    ingredient.name = payload.name.strip()
    ingredient.normalized_name = normalized_name
    ingredient.shopping_category_id = payload.shopping_category_id
    ingredient.preferred_unit_id = payload.preferred_unit_id
    ingredient.default_location_id = payload.default_location_id
    ingredient.perishable = payload.perishable
    ingredient.notes = payload.notes.strip() if payload.notes else None
    if isinstance(payload, IngredientUpdate):
        ingredient.active = payload.active

    ingredient.aliases.clear()
    for alias, normalized in aliases:
        ingredient.aliases.append(IngredientAlias(alias=alias, normalized_alias=normalized))

    db.add(ingredient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ingredient name or alias already exists") from exc
    db.refresh(ingredient)
    return _ingredient_or_404(db, ingredient.id)


@router.get("/ingredients", response_model=list[IngredientRead])
def list_ingredients(
    search: str | None = Query(default=None, max_length=120),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[Ingredient]:
    statement = (
        select(Ingredient)
        .options(selectinload(Ingredient.aliases))
        .outerjoin(IngredientAlias)
        .where(Ingredient.household_id == DEFAULT_HOUSEHOLD_ID)
    )
    if not include_inactive:
        statement = statement.where(Ingredient.active.is_(True))
    if search and normalize_name(search):
        term = f"%{normalize_name(search)}%"
        statement = statement.where(
            or_(Ingredient.normalized_name.like(term), IngredientAlias.normalized_alias.like(term))
        )
    statement = statement.distinct().order_by(Ingredient.name)
    return list(db.scalars(statement).unique())


@router.get("/ingredients/{ingredient_id}", response_model=IngredientRead)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)) -> Ingredient:
    return _ingredient_or_404(db, ingredient_id)


@router.post("/ingredients", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
def create_ingredient(payload: IngredientCreate, db: Session = Depends(get_db)) -> Ingredient:
    ingredient = Ingredient(
        household_id=DEFAULT_HOUSEHOLD_ID,
        name=payload.name.strip(),
        normalized_name=normalize_name(payload.name),
    )
    return _save_ingredient(db, ingredient, payload)


@router.put("/ingredients/{ingredient_id}", response_model=IngredientRead)
def update_ingredient(ingredient_id: int, payload: IngredientUpdate, db: Session = Depends(get_db)) -> Ingredient:
    ingredient = _ingredient_or_404(db, ingredient_id)
    return _save_ingredient(db, ingredient, payload)


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_ingredient(ingredient_id: int, db: Session = Depends(get_db)) -> None:
    ingredient = _ingredient_or_404(db, ingredient_id)
    ingredient.active = False
    db.commit()


@router.get("/tags", response_model=list[TagRead])
def list_tags(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[Tag]:
    statement = select(Tag).where(Tag.household_id == DEFAULT_HOUSEHOLD_ID)
    if not include_inactive:
        statement = statement.where(Tag.active.is_(True))
    return list(db.scalars(statement.order_by(Tag.category, Tag.name)))


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> Tag:
    normalized = normalize_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Tag name cannot be blank")
    tag = Tag(
        household_id=DEFAULT_HOUSEHOLD_ID,
        name=payload.name.strip(),
        normalized_name=normalized,
        category=payload.category.strip().upper(),
    )
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tag already exists") from exc
    db.refresh(tag)
    return tag


@router.put("/tags/{tag_id}", response_model=TagRead)
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None or tag.household_id != DEFAULT_HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Tag not found")
    normalized = normalize_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Tag name cannot be blank")
    tag.name = payload.name.strip()
    tag.normalized_name = normalized
    tag.category = payload.category.strip().upper()
    tag.active = payload.active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tag already exists") from exc
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_tag(tag_id: int, db: Session = Depends(get_db)) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None or tag.household_id != DEFAULT_HOUSEHOLD_ID:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.active = False
    db.commit()
