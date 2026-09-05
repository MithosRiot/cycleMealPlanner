from __future__ import annotations

from decimal import Decimal

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    from seed_test_db import configure_database


def seed_dashboard_alert_fixture() -> None:
    configure_database()

    from app.api.cycle_validation import validate_cycle
    from app.api.shopping import _cycle_or_404, _regenerate, _serialize
    from app.database.migrations import run_migrations
    from app.database.session import SessionLocal
    from app.models.inventory import InventoryLot, InventoryTransaction

    run_migrations()

    with SessionLocal() as db:
        lot = db.get(InventoryLot, 10)
        if lot is None:
            raise RuntimeError("Seeded Onion Inventory Lot 10 was not found. Run seed_test_db.py --reset first.")

        quantity = Decimal(lot.quantity)
        if quantity > 0:
            lot.quantity = Decimal("0")
            db.add(
                InventoryTransaction(
                    household_id=1,
                    lot_id=lot.id,
                    transaction_type="MANUAL_REMOVE",
                    quantity_delta=-quantity,
                    unit_id=lot.unit_id,
                    from_location_id=lot.location_id,
                    note="v0.9 dashboard alert test fixture",
                )
            )
            db.commit()

        cycle = _cycle_or_404(db, 1)
        shopping_list = _regenerate(db, cycle)
        shopping = _serialize(db, shopping_list, cycle)
        onion = next(item for item in shopping["items"] if item["ingredient_name"] == "Onion")
        shopping_shortages = [
            item
            for item in shopping["items"]
            if item["status"] == "PENDING" and Decimal(str(item["generated_quantity"])) > 0
        ]

        validation = validate_cycle(1, db)
        shortage = next(
            issue
            for issue in validation["issues"]
            if issue["code"] == "INVENTORY_SHORTAGE" and issue["context"].get("ingredient_id") == 10
        )

        print(
            "Dashboard alert fixture ready: "
            f"Onion Need {onion['required_quantity']} {onion['unit_code']}; "
            f"Have {onion['inventory_quantity']} {onion['unit_code']}; "
            f"Missing {onion['generated_quantity']} {onion['unit_code']}"
        )
        print(f"Validation alert: {shortage['message']}")
        print(
            "Expected Dashboard counts: "
            f"{len(validation['issues'])} validation; "
            f"{len(shopping_shortages)} shopping "
            f"({validation['error_count']} errors, {validation['warning_count']} warnings in Plan Validation)"
        )


if __name__ == "__main__":
    seed_dashboard_alert_fixture()
