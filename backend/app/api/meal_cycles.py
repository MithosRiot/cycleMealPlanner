import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Tag
from app.models.meal import Meal
from app.models.meal_cycle import CycleSlot, MealCycle, MealSlotDefinition
from app.schemas.meal_cycle import (
    MealCycleInput,
    MealCycleRead,
    MealCycleScheduleUpdate,
    MealSlotDefinitionInput,
    PopulationRulesUpdate,
    SmartPlanningPreferencesUpdate,
)
from app.services.normalization import normalize_name

router = APIRouter(prefix="/api/meal-cycles", tags=["meal-cycles"])
HOUSEHOLD_ID = 1


def _load_cycle(db: Session, cycle_id: int) -> MealCycle:
    cycle = db.scalar(select(MealCycle).where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID).options(selectinload(MealCycle.slot_definitions), selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition), selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal)))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Meal cycle not found")
    return cycle


def _normalize_slots(payload: MealCycleInput) -> list[MealSlotDefinitionInput]:
    labels: set[str] = set(); orders: set[int] = set(); normalized: list[MealSlotDefinitionInput] = []
    for slot in sorted(payload.slot_definitions, key=lambda item: item.sort_order):
        label = slot.label.strip(); label_key = normalize_name(label)
        if label_key in labels: raise HTTPException(status_code=400, detail=f"Duplicate slot label: {label}")
        if slot.sort_order in orders: raise HTTPException(status_code=400, detail="Slot sort_order values must be unique")
        labels.add(label_key); orders.add(slot.sort_order)
        normalized.append(MealSlotDefinitionInput(label=label, sort_order=slot.sort_order, serving_time=slot.serving_time))
    return normalized


def _same_cycle_structure(cycle: MealCycle, slot_inputs: list[MealSlotDefinitionInput], duration_days: int) -> bool:
    if cycle.duration_days != duration_days or len(cycle.slot_definitions) != len(slot_inputs):
        return False
    existing = sorted(cycle.slot_definitions, key=lambda item: item.sort_order)
    return all(
        current.sort_order == incoming.sort_order and normalize_name(current.label) == normalize_name(incoming.label)
        for current, incoming in zip(existing, slot_inputs, strict=True)
    )


def _apply_cycle(db: Session, cycle: MealCycle, payload: MealCycleInput) -> None:
    slot_inputs = _normalize_slots(payload)
    same_structure = bool(cycle.id) and _same_cycle_structure(cycle, slot_inputs, payload.duration_days)

    cycle.name = payload.name.strip(); cycle.normalized_name = normalize_name(payload.name); cycle.duration_days = payload.duration_days; cycle.start_date = payload.start_date; cycle.notes = payload.notes; cycle.status = "DRAFT"

    if same_structure:
        definitions = sorted(cycle.slot_definitions, key=lambda item: item.sort_order)
        for definition, slot in zip(definitions, slot_inputs, strict=True):
            definition.label = slot.label
            definition.sort_order = slot.sort_order
            definition.serving_time = slot.serving_time
        return

    cycle.slots.clear(); db.flush(); cycle.slot_definitions.clear(); db.flush()
    definitions = [MealSlotDefinition(label=slot.label, sort_order=slot.sort_order, serving_time=slot.serving_time) for slot in slot_inputs]
    cycle.slot_definitions.extend(definitions); db.flush()
    for day_number in range(1, payload.duration_days + 1):
        for definition in definitions:
            cycle.slots.append(CycleSlot(slot_definition_id=definition.id, day_number=day_number, sort_order=definition.sort_order))


def _validate_rule_ids(db: Session, meal_ids: set[int]) -> None:
    if not meal_ids: return
    active_ids = set(db.scalars(select(Meal.id).where(Meal.household_id == HOUSEHOLD_ID, Meal.active.is_(True), Meal.id.in_(meal_ids))))
    missing = meal_ids - active_ids
    if missing: raise HTTPException(status_code=422, detail=f"Unknown or archived Meal: {min(missing)}")


@router.get("", response_model=list[MealCycleRead])
def list_meal_cycles(db: Session = Depends(get_db)) -> list[MealCycle]:
    return list(db.scalars(select(MealCycle).where(MealCycle.household_id == HOUSEHOLD_ID).options(selectinload(MealCycle.slot_definitions), selectinload(MealCycle.slots).selectinload(CycleSlot.slot_definition), selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal)).order_by(MealCycle.id.desc())).unique())


@router.get("/{cycle_id}", response_model=MealCycleRead)
def get_meal_cycle(cycle_id: int, db: Session = Depends(get_db)) -> MealCycle: return _load_cycle(db, cycle_id)


@router.post("", response_model=MealCycleRead, status_code=status.HTTP_201_CREATED)
def create_meal_cycle(payload: MealCycleInput, db: Session = Depends(get_db)) -> MealCycle:
    cycle = MealCycle(household_id=HOUSEHOLD_ID, name=payload.name.strip(), normalized_name=normalize_name(payload.name), duration_days=payload.duration_days, status="DRAFT", start_date=payload.start_date, notes=payload.notes, population_rules="{}", smart_preferences="{}")
    db.add(cycle)
    try: _apply_cycle(db, cycle, payload); db.commit()
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Meal cycle name already exists") from exc
    return _load_cycle(db, cycle.id)


@router.put("/{cycle_id}", response_model=MealCycleRead)
def update_meal_cycle(cycle_id: int, payload: MealCycleInput, db: Session = Depends(get_db)) -> MealCycle:
    cycle = _load_cycle(db, cycle_id)
    try: _apply_cycle(db, cycle, payload); db.commit()
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Meal cycle name already exists") from exc
    return _load_cycle(db, cycle.id)


@router.put("/{cycle_id}/schedule", response_model=MealCycleRead)
def update_cycle_schedule(cycle_id: int, payload: MealCycleScheduleUpdate, db: Session = Depends(get_db)) -> MealCycle:
    cycle = _load_cycle(db, cycle_id)
    definitions = {item.id: item for item in cycle.slot_definitions}
    unknown = set(payload.serving_times) - set(definitions)
    if unknown: raise HTTPException(status_code=422, detail=f"Unknown slot definition: {min(unknown)}")
    cycle.start_date = payload.start_date
    for definition_id, serving_time in payload.serving_times.items(): definitions[definition_id].serving_time = serving_time
    db.commit(); return _load_cycle(db, cycle.id)


@router.put("/{cycle_id}/population-rules", response_model=MealCycleRead)
def update_population_rules(cycle_id: int, payload: PopulationRulesUpdate, db: Session = Depends(get_db)) -> MealCycle:
    cycle = _load_cycle(db, cycle_id); valid_slot_labels = {normalize_name(slot.label) for slot in cycle.slot_definitions}
    global_include = set(payload.include_meal_ids); global_exclude = set(payload.exclude_meal_ids)
    if global_include & global_exclude: raise HTTPException(status_code=422, detail="A Meal cannot be both included and excluded for the cycle")
    all_ids = global_include | global_exclude; normalized_slot_rules: dict[str, dict[str, list[int]]] = {}
    for label, rule in payload.slot_rules.items():
        normalized_label = normalize_name(label)
        if normalized_label not in valid_slot_labels: raise HTTPException(status_code=422, detail=f"Unknown slot label: {label}")
        include_ids = set(rule.include_meal_ids); exclude_ids = set(rule.exclude_meal_ids)
        if include_ids & exclude_ids: raise HTTPException(status_code=422, detail=f"A Meal cannot be both included and excluded for slot {label}")
        all_ids |= include_ids | exclude_ids; normalized_slot_rules[normalized_label] = {"include_meal_ids": sorted(include_ids), "exclude_meal_ids": sorted(exclude_ids)}
    _validate_rule_ids(db, all_ids)
    cycle.population_rules = json.dumps({"include_meal_ids": sorted(global_include), "exclude_meal_ids": sorted(global_exclude), "slot_rules": normalized_slot_rules}, sort_keys=True); db.commit(); return _load_cycle(db, cycle.id)


@router.put("/{cycle_id}/smart-preferences", response_model=MealCycleRead)
def update_smart_preferences(cycle_id: int, payload: SmartPlanningPreferencesUpdate, db: Session = Depends(get_db)) -> MealCycle:
    cycle = _load_cycle(db, cycle_id); tag_weights = {int(tag_id): float(weight) for tag_id, weight in payload.tag_weights.items()}; invalid_weights = [tag_id for tag_id, weight in tag_weights.items() if weight <= 0 or weight > 10]
    if invalid_weights: raise HTTPException(status_code=422, detail=f"Tag weight must be greater than 0 and at most 10: {min(invalid_weights)}")
    if tag_weights:
        active_tag_ids = set(db.scalars(select(Tag.id).where(Tag.household_id == HOUSEHOLD_ID, Tag.active.is_(True), Tag.id.in_(set(tag_weights)))))
        missing = set(tag_weights) - active_tag_ids
        if missing: raise HTTPException(status_code=422, detail=f"Unknown or archived Tag: {min(missing)}")
    cycle.smart_preferences = json.dumps({"repeat_spacing_days": payload.repeat_spacing_days, "favorite_boost": payload.favorite_boost, "history_penalty": payload.history_penalty, "tag_weights": {str(tag_id): weight for tag_id, weight in sorted(tag_weights.items())}}, sort_keys=True); db.commit(); return _load_cycle(db, cycle.id)


@router.delete("/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_cycle(cycle_id: int, db: Session = Depends(get_db)) -> None:
    cycle = _load_cycle(db, cycle_id); db.delete(cycle); db.commit()
