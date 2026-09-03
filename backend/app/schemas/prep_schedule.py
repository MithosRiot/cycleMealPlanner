from datetime import datetime

from pydantic import BaseModel


class PrepScheduleTaskRead(BaseModel):
    planned_meal_id: int
    cycle_slot_id: int
    meal_id: int
    meal_name: str
    recipe_id: int
    recipe_name: str
    advance_prep_id: int
    task_type: str
    title: str
    instructions: str | None
    prep_group_id: int | None
    prep_group_name: str | None
    lead_time_minutes: int
    duration_minutes: int | None
    serving_datetime: datetime | None
    start_datetime: datetime | None
    end_datetime: datetime | None
    unresolved_reason: str | None


class PrepScheduleRead(BaseModel):
    meal_cycle_id: int
    meal_cycle_name: str
    tasks: list[PrepScheduleTaskRead]
