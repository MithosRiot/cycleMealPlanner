from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.gather import TOLERANCE, _build_cycle, _cycle_or_404
from app.database.session import get_db
from app.models.reference import InventoryLocation
from app.schemas.gather import GatherLocationCycleRead

router = APIRouter(tags=["gather"])
HOUSEHOLD_ID = 1


def _location_metadata(locations: dict[int, InventoryLocation], location_id: int) -> tuple[str, tuple]:
    chain: list[InventoryLocation] = []
    seen: set[int] = set()
    current = locations.get(location_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        current = locations.get(current.parent_location_id) if current.parent_location_id is not None else None
    chain.reverse()
    path = " / ".join(item.name for item in chain) or f"Location {location_id}"
    order = tuple((item.sort_order, item.name.casefold(), item.id) for item in chain)
    return path, order


def _build_location_pick_list(db: Session, cycle_id: int) -> dict:
    cycle = _cycle_or_404(db, cycle_id)
    gather = _build_cycle(db, cycle)
    locations = {
        row.id: row
        for row in db.scalars(
            select(InventoryLocation).where(InventoryLocation.household_id == HOUSEHOLD_ID)
        )
    }

    grouped: dict[int, dict[tuple[int, int], dict]] = {}
    incomplete: list[dict] = []

    for requirement in gather["requirements"]:
        remaining = Decimal(requirement["shortage_quantity"])
        if remaining > TOLERANCE:
            incomplete.append({
                "planned_meal_id": requirement["planned_meal_id"],
                "meal_name": requirement["meal_name"],
                "day_number": requirement["day_number"],
                "slot_label": requirement["slot_label"],
                "meal_recipe_id": requirement["meal_recipe_id"],
                "recipe_id": requirement["recipe_id"],
                "recipe_ingredient_id": requirement["recipe_ingredient_id"],
                "ingredient_id": requirement["ingredient_id"],
                "ingredient_name": requirement["ingredient_name"],
                "required_quantity": requirement["required_quantity"],
                "selected_quantity": requirement["selected_quantity"],
                "remaining_quantity": remaining,
                "unit_id": requirement["unit_id"],
                "unit_code": requirement["unit_code"],
            })

        for selection in requirement["selections"]:
            location_id = selection["location_id"]
            key = (selection["lot_id"], selection["unit_id"])
            picks = grouped.setdefault(location_id, {})
            pick = picks.get(key)
            if pick is None:
                pick = {
                    "lot_id": selection["lot_id"],
                    "ingredient_id": requirement["ingredient_id"],
                    "ingredient_name": requirement["ingredient_name"],
                    "quantity": Decimal("0"),
                    "unit_id": selection["unit_id"],
                    "unit_code": selection["unit_code"],
                    "expiration_date": selection["expiration_date"],
                    "opened_date": selection["opened_date"],
                    "frozen_date": selection["frozen_date"],
                    "thawed_date": selection["thawed_date"],
                    "sources": [],
                }
                picks[key] = pick
            quantity = Decimal(selection["quantity"])
            pick["quantity"] += quantity
            pick["sources"].append({
                "planned_meal_id": requirement["planned_meal_id"],
                "meal_name": requirement["meal_name"],
                "day_number": requirement["day_number"],
                "slot_label": requirement["slot_label"],
                "meal_recipe_id": requirement["meal_recipe_id"],
                "recipe_id": requirement["recipe_id"],
                "recipe_ingredient_id": requirement["recipe_ingredient_id"],
                "ingredient_id": requirement["ingredient_id"],
                "ingredient_name": requirement["ingredient_name"],
                "quantity": quantity,
                "unit_id": selection["unit_id"],
                "unit_code": selection["unit_code"],
            })

    location_groups: list[tuple[tuple, dict]] = []
    for location_id, picks_by_key in grouped.items():
        location = locations.get(location_id)
        path, order = _location_metadata(locations, location_id)
        picks = list(picks_by_key.values())
        for pick in picks:
            pick["sources"].sort(key=lambda row: (row["day_number"], row["slot_label"], row["meal_name"], row["planned_meal_id"]))
        picks.sort(key=lambda row: (row["ingredient_name"].casefold(), row["lot_id"], row["unit_code"]))
        location_groups.append((order, {
            "location_id": location_id,
            "location_name": location.name if location else f"Location {location_id}",
            "location_path": path,
            "picks": picks,
        }))

    location_groups.sort(key=lambda item: item[0])
    incomplete.sort(key=lambda row: (row["day_number"], row["slot_label"], row["meal_name"], row["ingredient_name"].casefold()))
    return {
        "meal_cycle_id": cycle.id,
        "meal_cycle_name": cycle.name,
        "complete": len(incomplete) == 0,
        "locations": [item[1] for item in location_groups],
        "incomplete_requirements": incomplete,
    }


@router.get("/api/meal-cycles/{cycle_id}/gather/by-location", response_model=GatherLocationCycleRead)
def get_gather_by_location(cycle_id: int, db: Session = Depends(get_db)) -> dict:
    return _build_location_pick_list(db, cycle_id)
