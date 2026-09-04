import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.completion import MealCompletion
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.planned_meal import PlannedMeal
from app.models.production_coverage import ProductionCoverageReservation
from app.models.reservation import InventoryReservation
from app.schemas.reservation import (
    InventoryAvailabilityRead,
    ProductionAvailabilityRead,
    ProductionCoverageCycleSummary,
    ReservationCycleSummary,
)
from app.services.inventory_availability import availability_rows
from app.services.production_coverage import production_availability_rows, reconcile_production_coverage

router = APIRouter(tags=["reservations"])
HOUSEHOLD_ID = 1


def _cycle(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(select(MealCycle).where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _completed_planned_meal_ids(db: Session) -> set[int]:
    return set(db.scalars(select(MealCompletion.planned_meal_id).where(MealCompletion.status == "FINALIZED")))


def _requirements(db: Session, cycle_id: int) -> list[dict]:
    completed_ids = _completed_planned_meal_ids(db)
    rows = db.execute(
        select(PlannedMeal.id, PlannedMeal.scaled_components, PlannedMeal.source_type)
        .join(CycleSlot, CycleSlot.id == PlannedMeal.cycle_slot_id)
        .where(CycleSlot.cycle_id == cycle_id)
    ).all()
    required: list[dict] = []
    for planned_meal_id, raw, source_type in rows:
        if int(planned_meal_id) in completed_ids or source_type != "SAVED_MEAL":
            continue
        try:
            components = json.loads(raw or "[]")
        except json.JSONDecodeError:
            components = []
        for component in components:
            meal_recipe_id = int(component.get("meal_recipe_id")) if component.get("meal_recipe_id") is not None else None
            recipe_id = int(component["recipe_id"])
            for ingredient in component.get("ingredients", []):
                quantity = Decimal(str(ingredient.get("quantity", "0")))
                if quantity <= 0:
                    continue
                required.append({
                    "planned_meal_id": int(planned_meal_id),
                    "meal_recipe_id": meal_recipe_id,
                    "recipe_id": recipe_id,
                    "recipe_ingredient_id": int(ingredient["recipe_ingredient_id"]) if ingredient.get("recipe_ingredient_id") is not None else None,
                    "ingredient_id": int(ingredient["ingredient_id"]),
                    "quantity": quantity,
                    "unit_id": int(ingredient["unit_id"]),
                })
    return required


def _key(row: dict | InventoryReservation) -> tuple[int, int | None, int | None]:
    if isinstance(row, InventoryReservation):
        return row.planned_meal_id, row.meal_recipe_id, row.recipe_ingredient_id
    return row["planned_meal_id"], row["meal_recipe_id"], row["recipe_ingredient_id"]


def _summary(db: Session, cycle_id: int) -> ReservationCycleSummary:
    reservations = list(db.scalars(select(InventoryReservation).where(InventoryReservation.cycle_id == cycle_id).order_by(InventoryReservation.id)))
    return ReservationCycleSummary(
        cycle_id=cycle_id,
        active_count=sum(1 for row in reservations if row.status == "ACTIVE"),
        released_count=sum(1 for row in reservations if row.status == "RELEASED"),
        reservations=reservations,
    )


def _coverage_summary(db: Session, cycle_id: int) -> ProductionCoverageCycleSummary:
    reservations = list(db.scalars(
        select(ProductionCoverageReservation)
        .where(ProductionCoverageReservation.cycle_id == cycle_id)
        .order_by(ProductionCoverageReservation.id)
    ))
    return ProductionCoverageCycleSummary(
        cycle_id=cycle_id,
        active_count=sum(1 for row in reservations if row.status == "ACTIVE"),
        released_count=sum(1 for row in reservations if row.status == "RELEASED"),
        shortage_count=sum(1 for row in reservations if row.status == "ACTIVE" and Decimal(row.shortage_quantity) > 0),
        reservations=reservations,
    )


@router.get("/api/meal-cycles/{cycle_id}/reservations", response_model=ReservationCycleSummary)
def get_cycle_reservations(cycle_id: int, db: Session = Depends(get_db)) -> ReservationCycleSummary:
    _cycle(db, cycle_id)
    return _summary(db, cycle_id)


@router.post("/api/meal-cycles/{cycle_id}/reservations/regenerate", response_model=ReservationCycleSummary)
def regenerate_cycle_reservations(cycle_id: int, db: Session = Depends(get_db)) -> ReservationCycleSummary:
    _cycle(db, cycle_id)
    requirements = _requirements(db, cycle_id)
    completed_ids = _completed_planned_meal_ids(db)
    existing = list(db.scalars(select(InventoryReservation).where(InventoryReservation.cycle_id == cycle_id)))
    existing_by_key = {_key(row): row for row in existing}
    seen: set[tuple[int, int | None, int | None]] = set()

    for requirement in requirements:
        key = _key(requirement)
        seen.add(key)
        model = existing_by_key.get(key)
        if model is None:
            model = InventoryReservation(
                household_id=HOUSEHOLD_ID,
                cycle_id=cycle_id,
                planned_meal_id=requirement["planned_meal_id"],
                meal_recipe_id=requirement["meal_recipe_id"],
                recipe_id=requirement["recipe_id"],
                recipe_ingredient_id=requirement["recipe_ingredient_id"],
                ingredient_id=requirement["ingredient_id"],
                quantity=requirement["quantity"],
                unit_id=requirement["unit_id"],
                status="ACTIVE",
            )
            db.add(model)
        else:
            model.recipe_id = requirement["recipe_id"]
            model.ingredient_id = requirement["ingredient_id"]
            model.quantity = requirement["quantity"]
            model.unit_id = requirement["unit_id"]
            if model.planned_meal_id not in completed_ids:
                model.status = "ACTIVE"

    for model in existing:
        if (model.planned_meal_id in completed_ids or _key(model) not in seen) and model.status == "ACTIVE":
            model.status = "RELEASED"

    reconcile_production_coverage(db)
    db.commit()
    return _summary(db, cycle_id)


@router.get("/api/meal-cycles/{cycle_id}/production-coverage", response_model=ProductionCoverageCycleSummary)
def get_production_coverage(cycle_id: int, db: Session = Depends(get_db)) -> ProductionCoverageCycleSummary:
    _cycle(db, cycle_id)
    return _coverage_summary(db, cycle_id)


@router.post("/api/meal-cycles/{cycle_id}/production-coverage/reconcile", response_model=ProductionCoverageCycleSummary)
def reconcile_cycle_production_coverage(cycle_id: int, db: Session = Depends(get_db)) -> ProductionCoverageCycleSummary:
    _cycle(db, cycle_id)
    reconcile_production_coverage(db)
    db.commit()
    return _coverage_summary(db, cycle_id)


@router.get("/api/inventory-availability", response_model=list[InventoryAvailabilityRead])
def inventory_availability(db: Session = Depends(get_db)) -> list[InventoryAvailabilityRead]:
    return [InventoryAvailabilityRead(**row) for row in availability_rows(db)]


@router.get("/api/production-inventory-availability", response_model=list[ProductionAvailabilityRead])
def production_inventory_availability(db: Session = Depends(get_db)) -> list[ProductionAvailabilityRead]:
    return [ProductionAvailabilityRead(**row) for row in production_availability_rows(db)]
