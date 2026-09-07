from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal

try:
    from testdata import seed_test_db
except ModuleNotFoundError:
    import seed_test_db


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _create_ingredient(client, name: str, location_id: int, unit_id: int, *, perishable: bool = True) -> dict:
    response = client.post("/api/ingredients", json={
        "name": name,
        "shopping_category_id": None,
        "preferred_unit_id": unit_id,
        "default_location_id": location_id,
        "perishable": perishable,
        "notes": "Issue #106 expiration-resolution UAT fixture",
        "aliases": [],
    })
    if response.status_code != 201:
        raise RuntimeError(f"Could not create {name}: {response.text}")
    return response.json()


def _create_lot(client, ingredient_id: int, location_id: int, unit_id: int, expiration_date: date, note: str) -> dict:
    response = client.post("/api/inventory", json={
        "ingredient_id": ingredient_id,
        "location_id": location_id,
        "quantity": "5",
        "unit_id": unit_id,
        "purchase_date": date.today().isoformat(),
        "opened_date": None,
        "expiration_date": expiration_date.isoformat(),
        "frozen_date": None,
        "thawed_date": None,
        "notes": note,
        "transaction_type": "PURCHASE",
    })
    if response.status_code != 201:
        raise RuntimeError(f"Could not create UAT lot: {response.text}")
    return response.json()


def _create_recipe(client, name: str, ingredient_ids: list[int], unit_id: int) -> dict:
    response = client.post("/api/recipes", json={
        "name": name,
        "description": "Deterministic expiration-resolution UAT Recipe",
        "base_servings": "4",
        "serving_unit": "servings",
        "yield_quantity": None,
        "yield_unit_id": None,
        "prep_time_minutes": 5,
        "cook_time_minutes": 10,
        "notes": None,
        "favorite": False,
        "meal_types": ["DINNER"],
        "tag_ids": [],
        "prep_groups": [],
        "advance_prep": [],
        "equipment": [],
        "ingredients": [{
            "ingredient_id": ingredient_id,
            "prep_group_key": None,
            "quantity": "1",
            "unit_id": unit_id,
            "display_text": None,
            "preparation": None,
            "prep_method": None,
            "prep_size": None,
            "prep_state": None,
            "optional": False,
            "scaling_mode": "LINEAR",
            "required_state": "ANY",
            "sort_order": index,
            "notes": None,
            "substitutions": [],
        } for index, ingredient_id in enumerate(ingredient_ids)],
    })
    if response.status_code != 201:
        raise RuntimeError(f"Could not create {name}: {response.text}")
    return response.json()


def _create_meal(client, recipe_id: int) -> dict:
    response = client.post("/api/meals", json={
        "name": "Expiration UAT Recovery Meal",
        "description": "Uses both deterministic expiring Ingredients",
        "favorite": False,
        "meal_types": ["DINNER"],
        "tag_ids": [],
        "recipes": [{
            "recipe_id": recipe_id,
            "serving_multiplier": "1",
            "default_servings": "4",
            "sort_order": 0,
            "notes": None,
        }],
    })
    if response.status_code != 201:
        raise RuntimeError(f"Could not create Recovery Meal: {response.text}")
    return response.json()


def seed_fixture() -> None:
    seed_test_db.seed(reset=True)
    today = date.today()
    recovery_expiration = today + timedelta(days=2)
    freeze_expiration = today + timedelta(days=1)
    no_suggestion_expiration = today + timedelta(days=3)

    with _client() as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        each = units["each"]
        locations = client.get("/api/reference/inventory-locations").json()
        refrigerator = next(item for item in locations if item["name"] == "Refrigerator")
        freezer = next(item for item in locations if item["name"] == "Freezer")

        yogurt = _create_ingredient(client, "Expiration UAT Yogurt", refrigerator["id"], each["id"])
        spinach = _create_ingredient(client, "Expiration UAT Spinach", refrigerator["id"], each["id"])
        berries = _create_ingredient(client, "Expiration UAT Berries", refrigerator["id"], each["id"])
        shelf = _create_ingredient(
            client,
            "Expiration UAT Shelf Stable",
            refrigerator["id"],
            each["id"],
            perishable=False,
        )

        recovery_recipe = _create_recipe(
            client,
            "Expiration UAT Recovery Recipe",
            [yogurt["id"], spinach["id"]],
            each["id"],
        )
        _create_recipe(client, "Expiration UAT Yogurt Only Recipe", [yogurt["id"]], each["id"])
        recovery_meal = _create_meal(client, recovery_recipe["id"])

        yogurt_lot = _create_lot(
            client, yogurt["id"], refrigerator["id"], each["id"], recovery_expiration,
            "Ranked Recipe/Meal suggestion UAT lot",
        )
        spinach_lot = _create_lot(
            client, spinach["id"], refrigerator["id"], each["id"], recovery_expiration,
            "Second expiring Ingredient used by the top-ranked Recovery Meal",
        )
        berries_lot = _create_lot(
            client, berries["id"], refrigerator["id"], each["id"], freeze_expiration,
            "Freeze-only UAT lot",
        )
        shelf_lot = _create_lot(
            client, shelf["id"], refrigerator["id"], each["id"], no_suggestion_expiration,
            "Explicit no-suggestion UAT lot",
        )

        cycle_response = client.post("/api/meal-cycles", json={
            "name": "Expiration Resolution UAT",
            "duration_days": 3,
            "start_date": today.isoformat(),
            "notes": "Issue #106 deterministic UAT cycle",
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        })
        if cycle_response.status_code != 201:
            raise RuntimeError(f"Could not create expiration UAT cycle: {cycle_response.text}")
        cycle = cycle_response.json()

        # Dashboard intentionally chooses the ACTIVE cycle first. Empty slots are
        # required to demonstrate advisory plan actions, so the deterministic UAT
        # fixture marks this test cycle ACTIVE directly instead of running the
        # normal activation validator (which correctly rejects empty slots).
        from app.database.session import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("UPDATE meal_cycles SET lifecycle_status='DRAFT', activated_at=NULL WHERE lifecycle_status='ACTIVE'"))
            db.execute(text("UPDATE meal_cycles SET lifecycle_status='ACTIVE', activated_at=CURRENT_TIMESTAMP WHERE id=:id"), {"id": cycle["id"]})
            db.commit()

        resolutions = client.get(f"/api/meal-cycles/{cycle['id']}/expiration-resolutions?days=7")
        if resolutions.status_code != 200:
            raise RuntimeError(f"Could not evaluate expiration resolutions: {resolutions.text}")
        rows = resolutions.json()["resolutions"]
        yogurt_row = next(row for row in rows if row["lot_id"] == yogurt_lot["id"])
        berries_row = next(row for row in rows if row["lot_id"] == berries_lot["id"])
        shelf_row = next(row for row in rows if row["lot_id"] == shelf_lot["id"])

        if not yogurt_row["actions"] or yogurt_row["actions"][0].get("meal_id") != recovery_meal["id"]:
            raise RuntimeError(f"Unexpected Recovery Meal ranking: {yogurt_row}")
        freeze = next((action for action in berries_row["actions"] if action["kind"] == "FREEZE"), None)
        if freeze is None or freeze.get("freezer_location_id") != freezer["id"]:
            raise RuntimeError(f"Missing deterministic Freeze action: {berries_row}")
        if shelf_row["status"] != "NO_SUGGESTION":
            raise RuntimeError(f"Expected explicit no-suggestion state: {shelf_row}")

        print("Expiration Resolution UAT fixture ready:")
        print(f"  Cycle: Expiration Resolution UAT · ACTIVE · starts {today.isoformat()} · 3 Dinner slots empty")
        print(f"  Recovery Meal: Expiration UAT Recovery Meal · Recipe: Expiration UAT Recovery Recipe")
        print(f"  Ranked lot: Expiration UAT Yogurt · Lot {yogurt_lot['id']} · 5 each · Refrigerator · expires {recovery_expiration.isoformat()}")
        print(f"  Companion lot: Expiration UAT Spinach · Lot {spinach_lot['id']} · 5 each · Refrigerator · expires {recovery_expiration.isoformat()}")
        print("  Expected #1 Yogurt action: Plan Meal: Expiration UAT Recovery Meal · uses 2 expiring items · 0 additional Shopping lines · Day 1")
        print(f"  Freeze lot: Expiration UAT Berries · Lot {berries_lot['id']} · 5 each · Refrigerator · expires {freeze_expiration.isoformat()}")
        print("  Expected Berries action: Freeze Expiration UAT Berries · Freeze in Freezer")
        print(f"  No-suggestion lot: Expiration UAT Shelf Stable · Lot {shelf_lot['id']} · 5 each · Refrigerator · expires {no_suggestion_expiration.isoformat()}")
        print("  Expected no-suggestion text: No compatible Meal, Recipe, produced-stock placement, move, or safe freeze resolution is currently available.")


def verify_fixture() -> None:
    seed_test_db.configure_database()
    with _client() as client:
        cycles = client.get("/api/meal-cycles").json()
        cycle = next((item for item in cycles if item["name"] == "Expiration Resolution UAT"), None)
        if cycle is None or cycle["status"] != "ACTIVE":
            raise RuntimeError(f"Expiration UAT cycle is not ACTIVE: {cycle}")
        if any(slot["planned_meal"] is not None for slot in cycle["slots"]):
            raise RuntimeError("Expiration UAT cycle no longer has all three empty Dinner slots")

        ingredients = client.get("/api/ingredients").json()
        by_name = {item["name"]: item for item in ingredients}
        required_names = {
            "Expiration UAT Yogurt",
            "Expiration UAT Spinach",
            "Expiration UAT Berries",
            "Expiration UAT Shelf Stable",
        }
        missing = sorted(required_names - by_name.keys())
        if missing:
            raise RuntimeError(f"Missing expiration UAT Ingredients: {missing}")

        lots = client.get("/api/inventory", params={"include_empty": "true"}).json()
        lot_by_name = {}
        for name in required_names:
            ingredient_id = by_name[name]["id"]
            lot = next((item for item in lots if item["ingredient_id"] == ingredient_id), None)
            if lot is None:
                raise RuntimeError(f"Missing expiration UAT lot for {name}")
            if Decimal(lot["quantity"]) != Decimal("5"):
                raise RuntimeError(f"Unexpected expiration UAT quantity for {name}: {lot['quantity']}")
            lot_by_name[name] = lot

        response = client.get(f"/api/meal-cycles/{cycle['id']}/expiration-resolutions?days=7")
        if response.status_code != 200:
            raise RuntimeError(f"Expiration resolution endpoint failed: {response.text}")
        rows = response.json()["resolutions"]

        yogurt_row = next(row for row in rows if row["lot_id"] == lot_by_name["Expiration UAT Yogurt"]["id"])
        first = yogurt_row["actions"][0] if yogurt_row["actions"] else None
        if first is None or first["kind"] != "PLAN_MEAL" or first["candidate_name"] != "Expiration UAT Recovery Meal":
            raise RuntimeError(f"Unexpected top-ranked Yogurt resolution: {yogurt_row}")
        if first["matched_expiring_items"] != 2 or first["shopping_shortage_lines"] != 0 or first["target_day_number"] != 1:
            raise RuntimeError(f"Unexpected Yogurt ranking metrics: {first}")

        berries_row = next(row for row in rows if row["lot_id"] == lot_by_name["Expiration UAT Berries"]["id"])
        if not any(action["kind"] == "FREEZE" and action["freezer_location_name"] == "Freezer" for action in berries_row["actions"]):
            raise RuntimeError(f"Missing Berries Freeze resolution: {berries_row}")

        shelf_row = next(row for row in rows if row["lot_id"] == lot_by_name["Expiration UAT Shelf Stable"]["id"])
        if shelf_row["status"] != "NO_SUGGESTION" or shelf_row["actions"]:
            raise RuntimeError(f"Unexpected Shelf Stable no-suggestion state: {shelf_row}")

        print("Expiration Resolution UAT fixture verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic expiration-resolution UAT data.")
    parser.add_argument("--verify", action="store_true", help="Verify the existing expiration-resolution fixture before manual UAT.")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
