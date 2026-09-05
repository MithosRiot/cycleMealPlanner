from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    from seed_test_db import configure_database


def seed_use_soon_fixture() -> None:
    configure_database()
    from app.database.migrations import run_migrations
    from app.database.session import engine

    run_migrations()
    today = date.today()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM inventory_transactions WHERE lot_id=18"))
        connection.execute(text("DELETE FROM inventory_lots WHERE id=18"))
        connection.execute(text("""
            INSERT INTO inventory_lots
            (id, household_id, ingredient_id, source_type, source_id, source_name,
             location_id, quantity, unit_id, purchase_date, expiration_date, notes)
            VALUES
            (18,1,NULL,'LEFTOVER',9001,'Use Soon Leftover: Chicken Dinner',
             2,2.000000,16,:today,:expiration,'Deterministic v0.9 use-soon manual test fixture')
        """), {"today": today, "expiration": today + timedelta(days=2)})
        connection.execute(text("""
            INSERT INTO inventory_transactions
            (household_id, lot_id, transaction_type, quantity_delta, unit_id, to_location_id, note)
            VALUES (1,18,'PRODUCTION',2.000000,16,2,'Seeded v0.9 use-soon produced fixture')
        """))

    print(f"Use-soon fixture ready: Lot 18 expires {(today + timedelta(days=2)).isoformat()}")


if __name__ == "__main__":
    seed_use_soon_fixture()
