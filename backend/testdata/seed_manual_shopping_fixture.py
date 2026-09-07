from __future__ import annotations

import argparse

try:
    from testdata import seed_test_db
except ModuleNotFoundError:
    import seed_test_db


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _create_manual(client, cycle_id: int, payload: dict) -> dict:
    response = client.post(f"/api/shopping/{cycle_id}/manual-items", json=payload)
    if response.status_code != 201:
        raise RuntimeError(f"Could not create manual Shopping item {payload['name']}: {response.text}")
    return next(item for item in response.json()["items"] if item["name"] == payload["name"])


def seed_fixture() -> None:
    seed_test_db.seed(reset=True)
    with _client() as client:
        cycles = client.get("/api/meal-cycles").json()
        cycle = next(item for item in cycles if item["name"] == "Sample Week")
        regenerate = client.post(f"/api/shopping/{cycle['id']}/regenerate")
        if regenerate.status_code != 200:
            raise RuntimeError(f"Could not generate Sample Week Shopping list: {regenerate.text}")

        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        each = units["each"]
        locations = client.get("/api/reference/inventory-locations").json()
        refrigerator = next(item for item in locations if item["name"] == "Refrigerator")

        ingredient_response = client.post("/api/ingredients", json={
            "name": "Manual UAT Apples",
            "shopping_category_id": None,
            "preferred_unit_id": each["id"],
            "default_location_id": refrigerator["id"],
            "perishable": True,
            "notes": "PR #107 linked manual Shopping UAT Ingredient",
            "aliases": [],
        })
        if ingredient_response.status_code != 201:
            raise RuntimeError(f"Could not create Manual UAT Apples: {ingredient_response.text}")
        ingredient = ingredient_response.json()

        paper = _create_manual(client, cycle["id"], {
            "name": "Manual UAT Paper Towels",
            "quantity": "2",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": "Unlinked household item",
        })
        apples = _create_manual(client, cycle["id"], {
            "name": "Manual UAT Apples for Snacks",
            "quantity": "6",
            "unit_id": each["id"],
            "shopping_category_id": None,
            "ingredient_id": ingredient["id"],
            "notes": "Linked manual item; create Inventory only when explicitly requested",
        })
        remove_me = _create_manual(client, cycle["id"], {
            "name": "Manual UAT Remove Me",
            "quantity": "1",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": "Remove this pending item during UAT",
        })
        skip_me = _create_manual(client, cycle["id"], {
            "name": "Manual UAT Skip Me",
            "quantity": "1",
            "unit_id": None,
            "shopping_category_id": None,
            "ingredient_id": None,
            "notes": "Skip this item during UAT",
        })

        print("Manual Shopping UAT fixture ready:")
        print(f"  Cycle: Sample Week · ID {cycle['id']}")
        print(f"  Unlinked: Manual UAT Paper Towels · Item {paper['id']} · 2 · No Inventory link")
        print(f"  Linked: Manual UAT Apples for Snacks · Item {apples['id']} · 6 each · Ingredient Manual UAT Apples")
        print(f"  Linked intake target: Refrigerator · 6 each · purchase 2026-09-07 · expiration 2026-09-14")
        print(f"  Remove test: Manual UAT Remove Me · Item {remove_me['id']} · PENDING")
        print(f"  Skip test: Manual UAT Skip Me · Item {skip_me['id']} · PENDING")


def verify_fixture() -> None:
    seed_test_db.configure_database()
    with _client() as client:
        cycles = client.get("/api/meal-cycles").json()
        cycle = next((item for item in cycles if item["name"] == "Sample Week"), None)
        if cycle is None:
            raise RuntimeError("Sample Week cycle missing")
        response = client.get(f"/api/shopping/{cycle['id']}/manual-items")
        if response.status_code != 200:
            raise RuntimeError(f"Manual Shopping list unavailable: {response.text}")
        rows = {item["name"]: item for item in response.json()["items"]}
        expected = {
            "Manual UAT Paper Towels": ("2.000000", None, "PENDING"),
            "Manual UAT Apples for Snacks": ("6.000000", "Manual UAT Apples", "PENDING"),
            "Manual UAT Remove Me": ("1.000000", None, "PENDING"),
            "Manual UAT Skip Me": ("1.000000", None, "PENDING"),
        }
        for name, (quantity, ingredient_name, status) in expected.items():
            row = rows.get(name)
            if row is None:
                raise RuntimeError(f"Missing manual UAT item: {name}")
            if row["quantity"] != quantity or row["ingredient_name"] != ingredient_name or row["status"] != status:
                raise RuntimeError(f"Unexpected manual UAT item: {row}")

        before_ids = {name: rows[name]["id"] for name in expected}
        regenerate = client.post(f"/api/shopping/{cycle['id']}/regenerate")
        if regenerate.status_code != 200:
            raise RuntimeError(f"Could not regenerate generated Shopping demand: {regenerate.text}")
        after = {item["name"]: item for item in client.get(f"/api/shopping/{cycle['id']}/manual-items").json()["items"]}
        after_ids = {name: after[name]["id"] for name in expected}
        if after_ids != before_ids:
            raise RuntimeError(f"Manual items changed or duplicated during regeneration: before={before_ids}, after={after_ids}")
        print("Manual Shopping UAT fixture verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic manual Shopping UAT data.")
    parser.add_argument("--verify", action="store_true", help="Verify the existing manual Shopping fixture.")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
