import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.recipe import Recipe
from app.schemas.prep_schedule import PrepScheduleRead, PrepScheduleTaskRead

router = APIRouter(prefix="/api/meal-cycles", tags=["prep-schedule"])
HOUSEHOLD_ID = 1


@router.get("/{cycle_id}/prep-schedule", response_model=PrepScheduleRead)
def get_prep_schedule(cycle_id: int, db: Session = Depends(get_db)) -> PrepScheduleRead:
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

    planned = [slot.planned_meal for slot in cycle.slots if slot.planned_meal is not None]
    recipe_ids: set[int] = set()
    components_by_planned: dict[int, list[dict]] = {}
    for placement in planned:
        try:
            components = json.loads(placement.snapshot_components or "[]")
        except json.JSONDecodeError:
            components = []
        components_by_planned[placement.id] = components
        recipe_ids.update(int(item["recipe_id"]) for item in components if item.get("recipe_id") is not None)

    recipes = list(
        db.scalars(
            select(Recipe)
            .where(Recipe.id.in_(recipe_ids))
            .options(selectinload(Recipe.advance_prep), selectinload(Recipe.prep_groups))
        ).unique()
    ) if recipe_ids else []
    recipe_map = {recipe.id: recipe for recipe in recipes}

    tasks: list[PrepScheduleTaskRead] = []
    for placement in planned:
        serving_datetime = placement.scheduled_datetime
        unresolved_reason = None if serving_datetime is not None else "Cycle start date and slot serving time are required"
        for component in components_by_planned.get(placement.id, []):
            recipe = recipe_map.get(int(component.get("recipe_id", 0)))
            if recipe is None:
                continue
            group_names = {group.id: group.name for group in recipe.prep_groups}
            for prep in sorted(recipe.advance_prep, key=lambda item: item.sort_order):
                start_datetime = serving_datetime - timedelta(minutes=prep.lead_time_minutes) if serving_datetime else None
                end_datetime = start_datetime + timedelta(minutes=prep.duration_minutes) if start_datetime and prep.duration_minutes is not None else start_datetime
                tasks.append(
                    PrepScheduleTaskRead(
                        planned_meal_id=placement.id,
                        cycle_slot_id=placement.cycle_slot_id,
                        meal_id=placement.meal_id,
                        meal_name=placement.snapshot_name,
                        recipe_id=recipe.id,
                        recipe_name=recipe.name,
                        advance_prep_id=prep.id,
                        task_type=prep.task_type,
                        title=prep.title,
                        instructions=prep.instructions,
                        prep_group_id=prep.prep_group_id,
                        prep_group_name=group_names.get(prep.prep_group_id) if prep.prep_group_id is not None else None,
                        lead_time_minutes=prep.lead_time_minutes,
                        duration_minutes=prep.duration_minutes,
                        serving_datetime=serving_datetime,
                        start_datetime=start_datetime,
                        end_datetime=end_datetime,
                        unresolved_reason=unresolved_reason,
                    )
                )

    tasks.sort(key=lambda item: (item.start_datetime is None, item.start_datetime or item.serving_datetime, item.meal_name, item.recipe_name, item.title))
    return PrepScheduleRead(meal_cycle_id=cycle.id, meal_cycle_name=cycle.name, tasks=tasks)
