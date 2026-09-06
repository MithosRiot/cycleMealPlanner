from __future__ import annotations

import argparse
import json
from decimal import Decimal

try:
    from testdata import seed_test_db
except ModuleNotFoundError:
    import seed_test_db


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _create_ingredient(client, name: str, location_id: int, unit_id: int) -> dict:
    response = client.post("/api/ingredients", json={
        "name": name,
        "shopping_category_id": None,
        "preferred_unit_id": unit_id,
        "default_location_id": location_id,
        "perishable": True,
        "notes": "PR #105 waste/spoilage UAT fixture",
        "aliases": [],
    })
    if response.status_code != 201:
        raise RuntimeError(f"Could not create {name}: {response.text}")
    return response.json()


def _create_lot(client, ingredient_id: int, location_id: int, unit_id: int, note: str) -> dict:
    response = client.post("/api/inventory", json={
        "ingredient_id": ingredient_id,
        "location_id": location_id,
        "quantity": "5",
        "unit_id": unit_id,
        "purchase_date": "2026-09-06",
        "opened_date": None,
        "expiration_date": "2026-09-09",
        "frozen_date": None,
        "thawed_date": None,
        "notes": note,
        "transaction_type": "PURCHASE",
    })
    if response.status_code != 201:
        raise RuntimeError(f"Could not create UAT lot: {response.text}")
    return response.json()


def seed_fixture() -> None:
    seed_test_db.seed(reset=True)
    with _client() as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        each = units["each"]
        locations = client.get("/api/reference/inventory-locations").json()
        refrigerator = next(item for item in locations if item["name"] == "Refrigerator")
        pantry = next(item for item in locations if item["name"] == "Pantry")

        spoilage_ingredient = _create_ingredient(client, "Waste UAT Yogurt", refrigerator["id"], each["id"])
        spoilage_lot = _create_lot(
            client,
            spoilage_ingredient["id"],
            refrigerator["id"],
            each["id"],
            "Unreserved lot for spoilage UAT",
        )

        protected_ingredient = _create_ingredient(client, "Waste UAT Reserved Produce", pantry["id"], each["id"])
        protected_lot = _create_lot(
            client,
            protected_ingredient["id"],
            pantry["id"],
            each["id"],
            "5 each physical; 4 each protected by ACTIVE reservation",
        )

        recipe_response = client.post("/api/recipes", json={
            "name": "Waste UAT Reserved Recipe",
            "description": "Reservation protection fixture",
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
                "ingredient_id": protected_ingredient["id"],
                "prep_group_key": None,
                "quantity": "4",
                "unit_id": each["id"],
                "display_text": None,
                "preparation": None,
                "prep_method": None,
                "prep_size": None,
                "prep_state": None,
                "optional": False,
                "scaling_mode": "LINEAR",
                "required_state": "ANY",
                "sort_order": 0,
                "notes": None,
                "substitutions": [],
            }],
        })
        if recipe_response.status_code != 201:
            raise RuntimeError(f"Could not create reserved Recipe: {recipe_response.text}")
        recipe = recipe_response.json()

        meal_response = client.post("/api/meals", json={
            "name": "Waste UAT Reserved Meal",
            "description": "Reservation protection fixture",
            "favorite": False,
            "meal_types": ["DINNER"],
            "tag_ids": [],
            "recipes": [{
                "recipe_id": recipe["id"],
                "serving_multiplier": "1",
                "default_servings": "4",
                "sort_order": 0,
                "notes": None,
            }],
        })
        if meal_response.status_code != 201:
            raise RuntimeError(f"Could not create reserved Meal: {meal_response.text}")
        meal = meal_response.json()

        cycle_response = client.post("/api/meal-cycles", json={
            "name": "Waste UAT Reservation Cycle",
            "duration_days": 1,
            "start_date": "2026-09-06",
            "notes": "PR #105 reservation protection fixture",
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        })
        if cycle_response.status_code != 201:
            raise RuntimeError(f"Could not create reservation cycle: {cycle_response.text}")
        cycle = cycle_response.json()

        planned_response = client.post(
            f"/api/meal-cycles/{cycle['id']}/slots/{cycle['slots'][0]['id']}/planned-meal",
            json={"meal_id": meal["id"]},
        )
        if planned_response.status_code != 201:
            raise RuntimeError(f"Could not create reserved planned Meal: {planned_response.text}")
        planned = planned_response.json()
        component = json.loads(planned["scaled_components"])[0]

        from app.database.session import SessionLocal
        from app.models.reservation import InventoryReservation
        with SessionLocal() as db:
            db.add(InventoryReservation(
                household_id=1,
                cycle_id=cycle["id"],
                planned_meal_id=planned["id"],
                meal_recipe_id=component["meal_recipe_id"],
                recipe_id=recipe["id"],
                recipe_ingredient_id=component["ingredients"][0]["recipe_ingredient_id"],
                ingredient_id=protected_ingredient["id"],
                quantity=Decimal("4"),
                unit_id=each["id"],
                status="ACTIVE",
            ))
            db.commit()

        print("Waste/Spoilage UAT fixture ready:")
        print(f"  Spoilage lot: Waste UAT Yogurt · Lot {spoilage_lot['id']} · 5 each · Refrigerator · unreserved")
        print(f"  Protected lot: Waste UAT Reserved Produce · Lot {protected_lot['id']} · 5 each · Pantry")
        print("  Protected reservation: 4 each ACTIVE; only 1 each may be discarded")


def verify_fixture() -> None:
    seed_test_db.configure_database()
    with _client() as client:
        ingredients = client.get("/api/ingredients", params={"include_archived": "true"}).json()
        by_name = {item["name"]: item for item in ingredients}
        for name in ("Waste UAT Yogurt", "Waste UAT Reserved Produce"):
            if name not in by_name:
                raise RuntimeError(f"Missing UAT Ingredient: {name}")

        lots = client.get("/api/inventory", params={"include_empty": "true"}).json()
        spoilage_lot = next((lot for lot in lots if lot["ingredient_id"] == by_name["Waste UAT Yogurt"]["id"]), None)
        protected_lot = next((lot for lot in lots if lot["ingredient_id"] == by_name["Waste UAT Reserved Produce"]["id"]), None)
        if spoilage_lot is None or Decimal(spoilage_lot["quantity"]) != Decimal("5"):
            raise RuntimeError(f"Unexpected spoilage UAT lot: {spoilage_lot}")
        if protected_lot is None or Decimal(protected_lot["quantity"]) != Decimal("5"):
            raise RuntimeError(f"Unexpected protected UAT lot: {protected_lot}")

        availability = client.get("/api/reservations/availability").json()
        protected = next((row for row in availability if row["ingredient_id"] == by_name["Waste UAT Reserved Produce"]["id"]), None)
        if protected is None:
            raise RuntimeError("Protected UAT Ingredient is missing from availability")
        if Decimal(protected["physical_quantity"]) != Decimal("5") or Decimal(protected["reserved_quantity"]) != Decimal("4") or Decimal(protected["available_quantity"]) != Decimal("1"):
            raise RuntimeError(f"Unexpected protected availability: {protected}")

        print("Waste/Spoilage UAT fixture verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic Waste/Spoilage UAT data.")
    parser.add_argument("--verify", action="store_true", help="Verify the existing Waste/Spoilage fixture.")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
