from __future__ import annotations

import argparse
from decimal import Decimal

try:
    from testdata import seed_test_db
except ModuleNotFoundError:
    import seed_test_db


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def seed_fixture() -> None:
    seed_test_db.seed(reset=True)
    with _client() as client:
        locations = client.get("/api/reference/inventory-locations").json()
        refrigerator = next(item for item in locations if item["name"] == "Refrigerator")

        refreshed = client.post("/api/planned-meals/1/completion/refresh")
        if refreshed.status_code != 200:
            raise RuntimeError(f"Could not refresh seeded Chicken Dinner completion: {refreshed.text}")

        finalized = client.post("/api/planned-meals/1/completion/finalize")
        if finalized.status_code != 200:
            raise RuntimeError(f"Could not finalize seeded Chicken Dinner: {finalized.text}")
        if finalized.json()["shortages"]:
            raise RuntimeError(f"Seeded Chicken Dinner has unexpected shortages: {finalized.json()['shortages']}")

        preview = client.get("/api/planned-meals/1/completion/production-preview?actual_servings_produced=5")
        if preview.status_code != 200:
            raise RuntimeError(f"Could not preview seeded production: {preview.text}")
        output = next(item for item in preview.json()["outputs"] if item["output_name"] == "Cooked Chicken")

        committed = client.post("/api/planned-meals/1/completion/production", json={
            "actual_servings_produced": "5",
            "actual_servings_eaten": "4",
            "leftover_location_id": refrigerator["id"],
            "leftover_expiration_date": "2026-09-10",
            "leftover_notes": "History UAT leftover",
            "outputs": [{
                "recipe_output_id": output["recipe_output_id"],
                "component_key": output["component_key"],
                "actual_quantity": "1.5",
                "location_id": refrigerator["id"],
                "expiration_date": "2026-09-09",
                "notes": "History UAT output",
            }],
        })
        if committed.status_code != 200:
            raise RuntimeError(f"Could not commit seeded production: {committed.text}")

        leftover_lot_id = committed.json()["leftover"]["inventory_lot_id"]
        output_lot_id = committed.json()["outputs"][0]["inventory_lot_id"]
        print("Seeded History UAT fixture:")
        print("  Meal: Chicken Dinner")
        print("  Planned servings: 4")
        print("  Actual produced/eaten: 5 / 4")
        print(f"  Leftover: 1 serving, lot {leftover_lot_id}, use-by 2026-09-10")
        print(f"  Cooked Chicken output: 1.5 lb, lot {output_lot_id}, use-by 2026-09-09")


def verify_fixture() -> None:
    seed_test_db.configure_database()
    with _client() as client:
        meals = client.get("/api/history/meals")
        if meals.status_code != 200:
            raise RuntimeError(f"Meal history failed: {meals.text}")
        chicken = next((item for item in meals.json() if item["meal_name"] == "Chicken Dinner"), None)
        if chicken is None:
            raise RuntimeError("Chicken Dinner is missing from Meal history")
        if chicken["actual_servings_produced"] is None or Decimal(chicken["actual_servings_produced"]) != Decimal("5"):
            raise RuntimeError(f"Unexpected produced servings: {chicken['actual_servings_produced']}")
        if chicken["actual_servings_eaten"] is None or Decimal(chicken["actual_servings_eaten"]) != Decimal("4"):
            raise RuntimeError(f"Unexpected eaten servings: {chicken['actual_servings_eaten']}")
        if chicken["leftover"] is None or Decimal(chicken["leftover"]["leftover_servings"]) != Decimal("1"):
            raise RuntimeError(f"Unexpected leftover history: {chicken['leftover']}")
        output = next((item for item in chicken["outputs"] if item["output_name"] == "Cooked Chicken"), None)
        if output is None or Decimal(output["actual_quantity"]) != Decimal("1.5"):
            raise RuntimeError(f"Unexpected output history: {output}")

        leftover_lot_id = chicken["leftover"]["inventory_lot_id"]
        inventory = client.get("/api/history/inventory", params={"lot_id": leftover_lot_id, "transaction_type": "PRODUCTION"})
        if inventory.status_code != 200 or len(inventory.json()) != 1:
            raise RuntimeError(f"Unexpected leftover transaction history: {inventory.text}")
        transaction = inventory.json()[0]
        if transaction["source_type"] != "LEFTOVER" or transaction["source_name"] != "Leftover: Chicken Dinner":
            raise RuntimeError(f"Unexpected leftover transaction provenance: {transaction}")
        if Decimal(transaction["quantity_delta"]) != Decimal("1"):
            raise RuntimeError(f"Unexpected leftover transaction quantity: {transaction['quantity_delta']}")

        print("History UAT fixture verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic Meal and Inventory History UAT data.")
    parser.add_argument("--verify", action="store_true", help="Verify the already-seeded History fixture.")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
