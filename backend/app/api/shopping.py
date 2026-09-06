import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.models.ingredient import Ingredient
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.meal_cycle import CycleSlot, MealCycle
from app.models.reference import InventoryLocation, MeasurementUnit, ShoppingCategory
from app.models.shopping import ShoppingItemPurchase, ShoppingList, ShoppingListItem
from app.schemas.shopping import ShoppingItemAdjustment, ShoppingItemComplete, ShoppingListRead
from app.services.inventory_availability import availability_for
from app.services.units import convert_quantity

router = APIRouter(prefix="/api/shopping", tags=["shopping"])
HOUSEHOLD_ID = 1


def _cycle_or_404(db, cycle_id):
    cycle = db.scalar(select(MealCycle).where(MealCycle.id == cycle_id, MealCycle.household_id == HOUSEHOLD_ID).options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal)))
    if cycle is None: raise HTTPException(404, "Meal cycle not found")
    return cycle


def _shopping_list_or_404(db, cycle_id):
    value = db.scalar(select(ShoppingList).where(ShoppingList.meal_cycle_id == cycle_id, ShoppingList.household_id == HOUSEHOLD_ID).options(selectinload(ShoppingList.items).selectinload(ShoppingListItem.purchases)))
    if value is None: raise HTTPException(404, "Shopping list has not been generated")
    return value


def _item_or_404(shopping_list, item_id):
    value = next((row for row in shopping_list.items if row.id == item_id), None)
    if value is None: raise HTTPException(404, "Shopping list item not found")
    return value


def _substitution_satisfied(item, target_unit, units):
    total = Decimal("0")
    for purchase in item.purchases:
        if purchase.purchase_kind != "SUBSTITUTION": continue
        source = units.get(purchase.satisfied_unit_id or purchase.actual_unit_id)
        if source and source.unit_family == target_unit.unit_family:
            total += convert_quantity(Decimal(purchase.satisfied_quantity or purchase.actual_quantity), source, target_unit)
    return total


def _all_satisfied(item, target_unit, units):
    total = Decimal("0")
    for purchase in item.purchases:
        source = units.get(purchase.satisfied_unit_id or purchase.actual_unit_id)
        if source and source.unit_family == target_unit.unit_family:
            total += convert_quantity(Decimal(purchase.satisfied_quantity or purchase.actual_quantity), source, target_unit)
    return total


def _remaining(item, target_unit, units):
    desired = max(Decimal(item.generated_quantity) + Decimal(item.adjustment_quantity), Decimal("0"))
    return max(desired - _substitution_satisfied(item, target_unit, units), Decimal("0"))


def _serialize(db, shopping_list, cycle):
    ingredients = {x.id: x for x in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))}; categories = {x.id: x for x in db.scalars(select(ShoppingCategory))}; units = {x.id: x for x in db.scalars(select(MeasurementUnit))}; result = []
    for item in shopping_list.items:
        if cycle.status != "ACTIVE" and item.status == "SKIPPED" and Decimal(item.required_quantity or 0) == 0 and not item.purchases: continue
        ingredient = ingredients[item.ingredient_id]; category = categories.get(item.shopping_category_id); unit = units[item.unit_id]; remaining = _remaining(item, unit, units); all_satisfied = _all_satisfied(item, unit, units); purchases = []
        for purchase in item.purchases:
            pu = units[purchase.actual_unit_id]; su = units[purchase.satisfied_unit_id or purchase.actual_unit_id]; pi = ingredients.get(purchase.purchased_ingredient_id or item.ingredient_id)
            purchases.append({"id": purchase.id, "actual_quantity": purchase.actual_quantity, "actual_unit_id": pu.id, "actual_unit_code": pu.code, "purchased_ingredient_id": purchase.purchased_ingredient_id or item.ingredient_id, "purchased_ingredient_name": pi.name if pi else "Unknown Ingredient", "satisfied_quantity": purchase.satisfied_quantity or purchase.actual_quantity, "satisfied_unit_id": su.id, "satisfied_unit_code": su.code, "purchase_kind": purchase.purchase_kind, "purchase_date": purchase.purchase_date, "storage_location_id": purchase.storage_location_id, "expiration_date": purchase.expiration_date, "purchase_notes": purchase.purchase_notes, "inventory_lot_id": purchase.inventory_lot_id, "completed_at": purchase.completed_at})
        actual_unit = units.get(item.actual_unit_id) if item.actual_unit_id else None
        result.append({"id": item.id, "ingredient_id": item.ingredient_id, "ingredient_name": ingredient.name, "shopping_category_id": item.shopping_category_id, "shopping_category_name": category.name if category else "Uncategorized", "shopping_category_sort_order": category.sort_order if category else 9999, "unit_id": unit.id, "unit_code": unit.code, "unit_family": item.unit_family, "required_quantity": item.required_quantity, "inventory_quantity": item.inventory_quantity, "generated_quantity": item.generated_quantity, "adjustment_quantity": item.adjustment_quantity, "final_quantity": remaining, "satisfied_quantity": all_satisfied, "remaining_quantity": remaining, "source_trace": item.source_trace, "warning": item.warning, "status": item.status, "actual_quantity": item.actual_quantity, "actual_unit_id": item.actual_unit_id, "actual_unit_code": actual_unit.code if actual_unit else None, "purchase_date": item.purchase_date, "storage_location_id": item.storage_location_id, "expiration_date": item.expiration_date, "purchase_notes": item.purchase_notes, "inventory_lot_id": item.inventory_lot_id, "completed_at": item.completed_at, "baseline_required_quantity": item.baseline_required_quantity, "plan_delta_quantity": item.plan_delta_quantity, "purchased_excess_quantity": item.purchased_excess_quantity, "purchases": purchases})
    result.sort(key=lambda x: (x["shopping_category_sort_order"], x["shopping_category_name"], x["ingredient_name"], x["unit_family"]))
    return {"id": shopping_list.id, "meal_cycle_id": shopping_list.meal_cycle_id, "meal_cycle_name": cycle.name, "generated_at": shopping_list.generated_at, "items": result}


def _regenerate(db: Session, cycle: MealCycle, *, commit=True):
    units = {x.id: x for x in db.scalars(select(MeasurementUnit))}; ingredients = {x.id: x for x in db.scalars(select(Ingredient).where(Ingredient.household_id == HOUSEHOLD_ID))}
    existing = db.scalar(select(ShoppingList).where(ShoppingList.meal_cycle_id == cycle.id, ShoppingList.household_id == HOUSEHOLD_ID).options(selectinload(ShoppingList.items).selectinload(ShoppingListItem.purchases)))
    if existing is None:
        shopping_list = ShoppingList(household_id=HOUSEHOLD_ID, meal_cycle_id=cycle.id, generated_at=datetime.utcnow()); db.add(shopping_list); db.flush(); existing_by_key = {}
    else:
        shopping_list = existing; shopping_list.generated_at = datetime.utcnow(); existing_by_key = {(x.ingredient_id, x.unit_family): x for x in existing.items}
    requirements = defaultdict(list); families = defaultdict(set); manual = set()
    for slot in sorted(cycle.slots, key=lambda x: (x.day_number, x.sort_order, x.id)):
        planned = slot.planned_meal
        if planned is None: continue
        for component in json.loads(planned.scaled_components or "[]"):
            for row in component.get("ingredients", []):
                iid = int(row["ingredient_id"]); uid = int(row["unit_id"]); unit = units.get(uid)
                if unit is None: raise HTTPException(409, f"Measurement unit {uid} no longer exists")
                key = (iid, unit.unit_family); families[iid].add(unit.unit_family); requirements[key].append({"quantity": Decimal(str(row["quantity"])), "unit_id": uid, "planned_meal_id": planned.id, "cycle_slot_id": slot.id, "day_number": slot.day_number, "meal_name": planned.snapshot_name, "recipe_id": int(component["recipe_id"])})
                if row.get("manual_review"): manual.add(key)
    for ingredient in ingredients.values():
        if ingredient.active and ingredient.staple_enabled and ingredient.staple_unit_id and ingredient.staple_minimum is not None and ingredient.staple_target is not None:
            unit = units.get(ingredient.staple_unit_id)
            if unit: families[ingredient.id].add(unit.unit_family); requirements.setdefault((ingredient.id, unit.unit_family), [])
    seen = set()
    for key in sorted(requirements):
        seen.add(key); iid, family = key; ingredient = ingredients.get(iid)
        if ingredient is None: raise HTTPException(409, f"Ingredient {iid} no longer exists")
        rows = requirements[key]; preferred = units.get(ingredient.preferred_unit_id) if ingredient.preferred_unit_id else None; staple = units.get(ingredient.staple_unit_id) if ingredient.staple_unit_id else None
        target = preferred if preferred and preferred.unit_family == family else units[min(x["unit_id"] for x in rows)] if rows else staple
        if target is None or target.unit_family != family: continue
        required = Decimal("0"); trace = []
        for row in rows:
            required += convert_quantity(row["quantity"], units[row["unit_id"]], target); trace.append({"planned_meal_id": row["planned_meal_id"], "cycle_slot_id": row["cycle_slot_id"], "day_number": row["day_number"], "meal_name": row["meal_name"], "recipe_id": row["recipe_id"], "quantity": str(row["quantity"]), "unit_id": row["unit_id"]})
        _, reserved_elsewhere, available, _ = availability_for(db, iid, family, target, exclude_cycle_id=cycle.id, units=units); generated = max(required - available, Decimal("0")); warnings = []
        if ingredient.staple_enabled and staple and staple.unit_family == family and ingredient.staple_minimum is not None and ingredient.staple_target is not None:
            minimum = convert_quantity(Decimal(ingredient.staple_minimum), staple, target); target_stock = convert_quantity(Decimal(ingredient.staple_target), staple, target); projected = max(available - required, Decimal("0"))
            if projected < minimum: generated = max(required + target_stock - available, Decimal("0")); warnings.append(f"Staple stock would be {projected} {target.code}, below minimum {minimum}; replenish toward target {target_stock}."); trace.append({"source": "STAPLE", "minimum": str(minimum), "target": str(target_stock), "projected_free": str(projected), "unit_id": target.id})
        if len(families[iid]) > 1: warnings.append("Ingredient requirements use incompatible unit families and are kept separate.")
        if key in manual: warnings.append("One or more recipe ingredients use MANUAL scaling; review this quantity.")
        if reserved_elsewhere > 0: warnings.append(f"{reserved_elsewhere} {target.code} of physical inventory is reserved for other planned cycles.")
        item = existing_by_key.get(key)
        if item is None:
            item = ShoppingListItem(shopping_list_id=shopping_list.id, ingredient_id=iid, unit_family=family, adjustment_quantity=0, status="PENDING", baseline_required_quantity=required, plan_delta_quantity=0, purchased_excess_quantity=0); db.add(item)
        elif item.baseline_required_quantity is None: item.baseline_required_quantity = Decimal(item.required_quantity)
        item.shopping_category_id = ingredient.shopping_category_id; item.unit_id = target.id; item.required_quantity = required; item.inventory_quantity = available; item.generated_quantity = generated; item.source_trace = json.dumps(trace, sort_keys=True); item.warning = " ".join(warnings) or None; item.plan_delta_quantity = required - Decimal(item.baseline_required_quantity or 0); item.purchased_excess_quantity = max(_all_satisfied(item, target, units) - required, Decimal("0")); remaining = _remaining(item, target, units); item.status = "COMPLETED" if remaining <= 0 and item.purchases else "PENDING" if remaining > 0 else item.status
    for key, item in existing_by_key.items():
        if key in seen: continue
        target = units.get(item.unit_id)
        if target is None: continue
        if item.baseline_required_quantity is None: item.baseline_required_quantity = Decimal(item.required_quantity)
        item.required_quantity = 0; item.generated_quantity = 0; item.source_trace = "[]"; item.plan_delta_quantity = -Decimal(item.baseline_required_quantity or 0); item.purchased_excess_quantity = _all_satisfied(item, target, units); item.status = "COMPLETED" if item.purchases else "SKIPPED" if item.status == "PENDING" else item.status
    sid = shopping_list.id; db.flush()
    if commit: db.commit(); db.expire_all()
    return db.scalar(select(ShoppingList).where(ShoppingList.id == sid).options(selectinload(ShoppingList.items).selectinload(ShoppingListItem.purchases)).execution_options(populate_existing=True))


@router.get("/{cycle_id}", response_model=ShoppingListRead)
def get_shopping_list(cycle_id: int, db: Session = Depends(get_db)): return _serialize(db, _shopping_list_or_404(db, cycle_id), _cycle_or_404(db, cycle_id))


@router.post("/{cycle_id}/regenerate", response_model=ShoppingListRead)
def regenerate_shopping_list(cycle_id: int, db: Session = Depends(get_db)):
    cycle = _cycle_or_404(db, cycle_id); return _serialize(db, _regenerate(db, cycle), cycle)


@router.put("/{cycle_id}/items/{item_id}", response_model=ShoppingListRead)
def adjust_shopping_item(cycle_id: int, item_id: int, payload: ShoppingItemAdjustment, db: Session = Depends(get_db)):
    cycle = _cycle_or_404(db, cycle_id); sl = _shopping_list_or_404(db, cycle_id); item = _item_or_404(sl, item_id)
    if item.status != "PENDING": raise HTTPException(409, "Non-pending shopping items cannot be adjusted")
    item.adjustment_quantity = payload.adjustment_quantity; db.commit(); return _serialize(db, sl, cycle)


@router.post("/{cycle_id}/items/{item_id}/complete", response_model=ShoppingListRead)
def complete_shopping_item(cycle_id: int, item_id: int, payload: ShoppingItemComplete, db: Session = Depends(get_db)):
    cycle = _cycle_or_404(db, cycle_id); sl = _shopping_list_or_404(db, cycle_id); item = _item_or_404(sl, item_id)
    if payload.idempotency_key:
        prior = db.scalar(select(ShoppingItemPurchase).where(ShoppingItemPurchase.idempotency_key == payload.idempotency_key))
        if prior:
            if prior.shopping_list_item_id != item.id: raise HTTPException(409, "Purchase idempotency key was already used for another Shopping item")
            return _serialize(db, sl, cycle)
    if item.status != "PENDING": raise HTTPException(409, "Only pending Shopping demand can be purchased")
    units = {x.id: x for x in db.scalars(select(MeasurementUnit))}; target = units[item.unit_id]; actual_unit = units.get(payload.actual_unit_id)
    if actual_unit is None: raise HTTPException(400, "Measurement unit not found")
    purchased_iid = payload.purchased_ingredient_id or item.ingredient_id; purchased = db.scalar(select(Ingredient).where(Ingredient.id == purchased_iid, Ingredient.household_id == HOUSEHOLD_ID, Ingredient.active.is_(True)))
    if purchased is None: raise HTTPException(400, "Purchased Ingredient not found")
    substitution = purchased_iid != item.ingredient_id
    if not substitution and actual_unit.unit_family != item.unit_family: raise HTTPException(409, "Purchased unit must use the same measurement family as the shopping item")
    if substitution and (payload.satisfied_quantity is None or payload.satisfied_unit_id is None): raise HTTPException(422, "A substitution must state how much original demand it satisfies")
    satisfied_unit = units.get(payload.satisfied_unit_id or payload.actual_unit_id)
    if satisfied_unit is None or satisfied_unit.unit_family != item.unit_family: raise HTTPException(409, "Satisfied unit must use the original Shopping item's measurement family")
    satisfied_qty = payload.satisfied_quantity if payload.satisfied_quantity is not None else payload.actual_quantity; satisfied_target = convert_quantity(Decimal(satisfied_qty), satisfied_unit, target); before = _remaining(item, target, units)
    if satisfied_target > before: raise HTTPException(409, f"Purchase satisfies {satisfied_target} {target.code}, but only {before} {target.code} remains")
    location = db.get(InventoryLocation, payload.storage_location_id)
    if location is None or location.household_id != HOUSEHOLD_ID or not location.active: raise HTTPException(400, "Inventory location not found")
    lot = InventoryLot(household_id=HOUSEHOLD_ID, ingredient_id=purchased_iid, location_id=location.id, quantity=payload.actual_quantity, unit_id=actual_unit.id, purchase_date=payload.purchase_date, expiration_date=payload.expiration_date, notes=payload.notes.strip() if payload.notes else None); db.add(lot); db.flush(); db.add(InventoryTransaction(household_id=HOUSEHOLD_ID, lot_id=lot.id, transaction_type="PURCHASE", quantity_delta=payload.actual_quantity, unit_id=actual_unit.id, to_location_id=location.id, note=payload.notes.strip() if payload.notes else None))
    now = datetime.utcnow(); purchase = ShoppingItemPurchase(shopping_list_item_id=item.id, actual_quantity=payload.actual_quantity, actual_unit_id=actual_unit.id, purchased_ingredient_id=purchased_iid, satisfied_quantity=satisfied_qty, satisfied_unit_id=satisfied_unit.id, purchase_kind="SUBSTITUTION" if substitution else "STANDARD", idempotency_key=payload.idempotency_key, purchase_date=payload.purchase_date, storage_location_id=location.id, expiration_date=payload.expiration_date, purchase_notes=payload.notes.strip() if payload.notes else None, inventory_lot_id=lot.id, completed_at=now); db.add(purchase); db.flush()
    if not substitution: item.generated_quantity = max(Decimal(item.generated_quantity) - satisfied_target, Decimal("0"))
    after = _remaining(item, target, units); item.status = "COMPLETED" if after <= 0 else "PENDING"; item.actual_quantity = payload.actual_quantity; item.actual_unit_id = actual_unit.id; item.purchase_date = payload.purchase_date; item.storage_location_id = location.id; item.expiration_date = payload.expiration_date; item.purchase_notes = payload.notes.strip() if payload.notes else None; item.inventory_lot_id = lot.id; item.completed_at = now if after <= 0 else None
    db.commit(); db.expire_all(); return _serialize(db, _shopping_list_or_404(db, cycle_id), cycle)


@router.post("/{cycle_id}/items/{item_id}/skip", response_model=ShoppingListRead)
def skip_shopping_item(cycle_id: int, item_id: int, db: Session = Depends(get_db)):
    cycle = _cycle_or_404(db, cycle_id); sl = _shopping_list_or_404(db, cycle_id); item = _item_or_404(sl, item_id)
    if item.status != "PENDING": raise HTTPException(409, "Only pending Shopping demand can be skipped")
    item.status = "SKIPPED"; item.completed_at = datetime.utcnow(); db.commit(); return _serialize(db, sl, cycle)