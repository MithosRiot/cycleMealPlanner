from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.engines.recipe_scaling import scale_quantity
from app.models.recipe import Recipe
from app.models.recipe_output import RecipeDependency, RecipeOutput
from app.models.reference import MeasurementUnit
from app.schemas.recipe_output import (
    DependencyScaleRequest,
    DependencyScaleResponse,
    RecipeDependencyInput,
    RecipeDependencyRead,
    RecipeOutputBundle,
    RecipeOutputInput,
    RecipeOutputRead,
)
from app.services.normalization import normalize_name
from app.services.units import UnitConversionError, convert_quantity

router = APIRouter(prefix="/api/recipes", tags=["recipe-outputs"])
HOUSEHOLD_ID = 1


def _recipe(db: Session, recipe_id: int) -> Recipe:
    recipe = db.scalar(select(Recipe).where(Recipe.id == recipe_id, Recipe.household_id == HOUSEHOLD_ID))
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _output(db: Session, output_id: int) -> RecipeOutput:
    output = db.get(RecipeOutput, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Recipe output not found")
    return output


def _would_cycle(db: Session, consumer_recipe_id: int, source_recipe_id: int) -> bool:
    if consumer_recipe_id == source_recipe_id:
        return True
    frontier = [source_recipe_id]
    visited: set[int] = set()
    while frontier:
        recipe_id = frontier.pop()
        if recipe_id in visited:
            continue
        visited.add(recipe_id)
        deps = list(db.scalars(select(RecipeDependency).where(RecipeDependency.recipe_id == recipe_id)))
        if not deps:
            continue
        outputs = {
            output.id: output
            for output in db.scalars(select(RecipeOutput).where(RecipeOutput.id.in_([dep.recipe_output_id for dep in deps])))
        }
        for dep in deps:
            output = outputs.get(dep.recipe_output_id)
            if output is None:
                continue
            if output.recipe_id == consumer_recipe_id:
                return True
            frontier.append(output.recipe_id)
    return False


@router.get("/{recipe_id}/outputs-dependencies", response_model=RecipeOutputBundle)
def get_outputs_dependencies(recipe_id: int, include_inactive: bool = True, db: Session = Depends(get_db)) -> RecipeOutputBundle:
    _recipe(db, recipe_id)
    output_stmt = select(RecipeOutput).where(RecipeOutput.recipe_id == recipe_id)
    if not include_inactive:
        output_stmt = output_stmt.where(RecipeOutput.active.is_(True))
    outputs = list(db.scalars(output_stmt.order_by(RecipeOutput.sort_order, RecipeOutput.id)))
    dependencies = list(db.scalars(select(RecipeDependency).where(RecipeDependency.recipe_id == recipe_id).order_by(RecipeDependency.sort_order, RecipeDependency.id)))
    return RecipeOutputBundle(outputs=outputs, dependencies=dependencies)


@router.get("/outputs/available", response_model=list[RecipeOutputRead])
def available_outputs(exclude_recipe_id: int | None = None, db: Session = Depends(get_db)) -> list[RecipeOutput]:
    stmt = select(RecipeOutput).join(Recipe, Recipe.id == RecipeOutput.recipe_id).where(Recipe.household_id == HOUSEHOLD_ID, RecipeOutput.active.is_(True))
    if exclude_recipe_id is not None:
        stmt = stmt.where(RecipeOutput.recipe_id != exclude_recipe_id)
    return list(db.scalars(stmt.order_by(Recipe.name, RecipeOutput.sort_order, RecipeOutput.id)))


@router.post("/{recipe_id}/outputs", response_model=RecipeOutputRead, status_code=201)
def create_output(recipe_id: int, payload: RecipeOutputInput, db: Session = Depends(get_db)) -> RecipeOutput:
    _recipe(db, recipe_id)
    if db.get(MeasurementUnit, payload.unit_id) is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    normalized = normalize_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Output name cannot be blank")
    if db.scalar(select(RecipeOutput.id).where(RecipeOutput.recipe_id == recipe_id, RecipeOutput.normalized_name == normalized)) is not None:
        raise HTTPException(status_code=409, detail="Output name already exists for this Recipe")
    model = RecipeOutput(recipe_id=recipe_id, name=payload.name.strip(), normalized_name=normalized, quantity=payload.quantity, unit_id=payload.unit_id, notes=payload.notes.strip() if payload.notes else None, active=payload.active, sort_order=payload.sort_order)
    db.add(model); db.commit(); db.refresh(model)
    return model


@router.put("/{recipe_id}/outputs/{output_id}", response_model=RecipeOutputRead)
def update_output(recipe_id: int, output_id: int, payload: RecipeOutputInput, db: Session = Depends(get_db)) -> RecipeOutput:
    _recipe(db, recipe_id)
    model = _output(db, output_id)
    if model.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Recipe output not found")
    if db.get(MeasurementUnit, payload.unit_id) is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    normalized = normalize_name(payload.name)
    duplicate = db.scalar(select(RecipeOutput.id).where(RecipeOutput.recipe_id == recipe_id, RecipeOutput.normalized_name == normalized, RecipeOutput.id != output_id))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Output name already exists for this Recipe")
    model.name = payload.name.strip(); model.normalized_name = normalized; model.quantity = payload.quantity; model.unit_id = payload.unit_id; model.notes = payload.notes.strip() if payload.notes else None; model.active = payload.active; model.sort_order = payload.sort_order
    db.commit(); db.refresh(model)
    return model


@router.delete("/{recipe_id}/outputs/{output_id}", status_code=204)
def archive_output(recipe_id: int, output_id: int, db: Session = Depends(get_db)) -> None:
    _recipe(db, recipe_id)
    model = _output(db, output_id)
    if model.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Recipe output not found")
    model.active = False
    db.commit()


@router.post("/{recipe_id}/dependencies", response_model=RecipeDependencyRead, status_code=201)
def create_dependency(recipe_id: int, payload: RecipeDependencyInput, db: Session = Depends(get_db)) -> RecipeDependency:
    _recipe(db, recipe_id)
    output = _output(db, payload.recipe_output_id)
    if not output.active:
        raise HTTPException(status_code=400, detail="Archived Recipe output cannot be selected")
    source_recipe = _recipe(db, output.recipe_id)
    if _would_cycle(db, recipe_id, source_recipe.id):
        raise HTTPException(status_code=422, detail="Recipe dependency would create a cycle")
    source_unit = db.get(MeasurementUnit, output.unit_id); target_unit = db.get(MeasurementUnit, payload.unit_id)
    if source_unit is None or target_unit is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    try:
        convert_quantity(payload.quantity, target_unit, source_unit)
    except UnitConversionError as exc:
        raise HTTPException(status_code=422, detail="Dependency unit must be compatible with the output unit") from exc
    if db.scalar(select(RecipeDependency.id).where(RecipeDependency.recipe_id == recipe_id, RecipeDependency.recipe_output_id == payload.recipe_output_id)) is not None:
        raise HTTPException(status_code=409, detail="Recipe already depends on this output")
    model = RecipeDependency(recipe_id=recipe_id, recipe_output_id=payload.recipe_output_id, quantity=payload.quantity, unit_id=payload.unit_id, scaling_mode=payload.scaling_mode.upper(), notes=payload.notes.strip() if payload.notes else None, sort_order=payload.sort_order)
    db.add(model); db.commit(); db.refresh(model)
    return model


@router.put("/{recipe_id}/dependencies/{dependency_id}", response_model=RecipeDependencyRead)
def update_dependency(recipe_id: int, dependency_id: int, payload: RecipeDependencyInput, db: Session = Depends(get_db)) -> RecipeDependency:
    _recipe(db, recipe_id)
    model = db.get(RecipeDependency, dependency_id)
    if model is None or model.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Recipe dependency not found")
    output = _output(db, payload.recipe_output_id)
    if output.recipe_id == recipe_id or _would_cycle(db, recipe_id, output.recipe_id):
        raise HTTPException(status_code=422, detail="Recipe dependency would create a cycle")
    source_unit = db.get(MeasurementUnit, output.unit_id); target_unit = db.get(MeasurementUnit, payload.unit_id)
    if source_unit is None or target_unit is None:
        raise HTTPException(status_code=400, detail="Measurement unit not found")
    try:
        convert_quantity(payload.quantity, target_unit, source_unit)
    except UnitConversionError as exc:
        raise HTTPException(status_code=422, detail="Dependency unit must be compatible with the output unit") from exc
    duplicate = db.scalar(select(RecipeDependency.id).where(RecipeDependency.recipe_id == recipe_id, RecipeDependency.recipe_output_id == payload.recipe_output_id, RecipeDependency.id != dependency_id))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Recipe already depends on this output")
    model.recipe_output_id = payload.recipe_output_id; model.quantity = payload.quantity; model.unit_id = payload.unit_id; model.scaling_mode = payload.scaling_mode.upper(); model.notes = payload.notes.strip() if payload.notes else None; model.sort_order = payload.sort_order
    db.commit(); db.refresh(model)
    return model


@router.delete("/{recipe_id}/dependencies/{dependency_id}", status_code=204)
def delete_dependency(recipe_id: int, dependency_id: int, db: Session = Depends(get_db)) -> None:
    _recipe(db, recipe_id)
    model = db.get(RecipeDependency, dependency_id)
    if model is None or model.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Recipe dependency not found")
    db.delete(model); db.commit()


@router.post("/{recipe_id}/dependencies/scale", response_model=DependencyScaleResponse)
def scale_dependencies(recipe_id: int, payload: DependencyScaleRequest, db: Session = Depends(get_db)) -> dict:
    recipe = _recipe(db, recipe_id)
    scale_factor = Decimal(payload.requested_servings) / Decimal(recipe.base_servings)
    dependencies = list(db.scalars(select(RecipeDependency).where(RecipeDependency.recipe_id == recipe_id).order_by(RecipeDependency.sort_order, RecipeDependency.id)))
    rows = []
    for dependency in dependencies:
        output = _output(db, dependency.recipe_output_id)
        unit = db.get(MeasurementUnit, dependency.unit_id)
        if unit is None:
            raise HTTPException(status_code=409, detail="Stored dependency unit no longer exists")
        quantity, manual_review = scale_quantity(Decimal(dependency.quantity), scale_factor, dependency.scaling_mode)
        rows.append({"dependency_id": dependency.id, "recipe_output_id": output.id, "source_recipe_id": output.recipe_id, "output_name": output.name, "quantity": quantity, "unit_id": unit.id, "unit_code": unit.code, "scaling_mode": dependency.scaling_mode, "manual_review": manual_review})
    return {"recipe_id": recipe_id, "requested_servings": payload.requested_servings, "dependencies": rows}
