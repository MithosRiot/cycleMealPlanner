from __future__ import annotations

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    from seed_test_db import configure_database


def seed_dashboard_alert_fixture() -> None:
    configure_database()

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        lot = client.get("/api/inventory/10")
        lot.raise_for_status()
        quantity = lot.json()["quantity"]
        if float(quantity) > 0:
            removed = client.post(
                "/api/inventory/10/remove",
                json={"quantity": quantity, "note": "v0.9 dashboard alert test fixture"},
            )
            removed.raise_for_status()

        shopping = client.post("/api/shopping/1/regenerate")
        shopping.raise_for_status()
        onion = next(item for item in shopping.json()["items"] if item["ingredient_name"] == "Onion")
        validation = client.get("/api/meal-cycles/1/validate")
        validation.raise_for_status()
        shortage = next(
            issue
            for issue in validation.json()["issues"]
            if issue["code"] == "INVENTORY_SHORTAGE" and issue["context"].get("ingredient_id") == 10
        )

        print(
            "Dashboard alert fixture ready: "
            f"Onion Need {onion['required_quantity']} {onion['unit_code']}; "
            f"Have {onion['inventory_quantity']} {onion['unit_code']}; "
            f"Missing {onion['generated_quantity']} {onion['unit_code']}"
        )
        print(f"Validation alert: {shortage['message']}")


if __name__ == "__main__":
    seed_dashboard_alert_fixture()
