from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.session import engine
from app.main import app


def test_use_soon_orders_by_expiration_and_uses_available_quantity() -> None:
    suffix = uuid4().hex[:8]
    today = date.today()
    ingredient_id: int | None = None
    ingredient_lot_id: int | None = None
    produced_lot_id: int | None = None
    cycle_id: int | None = None

    with TestClient(app) as client:
        try:
            units = {row["code"]: row for row in client.get("/api/reference/units").json()}
            each = units["each"]
            serving = units["serving"]
            refrigerator = next(row for row in client.get("/api/reference/inventory-locations").json() if row["name"] == "Refrigerator")

            ingredient = client.post("/api/ingredients", json={
                "name": f"Use Soon Ingredient {suffix}",
                "shopping_category_id": None,
                "preferred_unit_id": each["id"],
                "default_location_id": refrigerator["id"],
                "perishable": True,
                "notes": None,
                "aliases": [],
            }).json()
            ingredient_id = int(ingredient["id"])
            added = client.post("/api/inventory", json={
                "ingredient_id": ingredient_id,
                "location_id": refrigerator["id"],
                "quantity": "5",
                "unit_id": each["id"],
                "purchase_date": today.isoformat(),
                "opened_date": None,
                "expiration_date": (today + timedelta(days=3)).isoformat(),
                "frozen_date": None,
                "thawed_date": None,
                "notes": "use-soon test ingredient",
                "transaction_type": "MANUAL_ADD",
            })
            assert added.status_code == 201
            ingredient_lot_id = int(added.json()["id"])

            cycle = client.post("/api/meal-cycles", json={
                "name": f"Use Soon Cycle {suffix}",
                "duration_days": 1,
                "start_date": today.isoformat(),
                "notes": None,
                "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
            }).json()
            cycle_id = int(cycle["id"])

            with engine.begin() as connection:
                result = connection.execute(text("""
                    INSERT INTO inventory_lots
                    (household_id, ingredient_id, source_type, source_id, source_name, location_id,
                     quantity, unit_id, purchase_date, expiration_date, notes)
                    VALUES (1,NULL,'LEFTOVER',99001,'Use Soon Leftover',:location,3,:unit,:today,:expiration,'use-soon produced test')
                    RETURNING id
                """), {
                    "location": refrigerator["id"],
                    "unit": serving["id"],
                    "today": today,
                    "expiration": today + timedelta(days=1),
                })
                produced_lot_id = int(result.scalar_one())
                connection.execute(text("""
                    INSERT INTO production_coverage_reservations
                    (household_id,cycle_id,planned_meal_id,cycle_slot_id,source_origin_planned_meal_id,
                     source_type,source_record_id,lot_id,requested_quantity,reserved_quantity,shortage_quantity,
                     unit_id,status,created_at,updated_at)
                    VALUES (1,:cycle,99002,99003,99004,'LEFTOVER',99001,:lot,2,2,0,:unit,'ACTIVE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                """), {"cycle": cycle_id, "lot": produced_lot_id, "unit": serving["id"]})

            response = client.get("/api/dashboard/use-soon?days=7")
            assert response.status_code == 200
            rows = response.json()["recommendations"]
            produced = next(row for row in rows if row["lot_id"] == produced_lot_id)
            ingredient_row = next(row for row in rows if row["lot_id"] == ingredient_lot_id)

            assert rows.index(produced) < rows.index(ingredient_row)
            assert produced["source_type"] == "LEFTOVER"
            assert produced["available_quantity"] == "1.000000"
            assert produced["days_remaining"] == 1
            assert ingredient_row["source_type"] == "INGREDIENT"
            assert ingredient_row["available_quantity"] == "5.000000"
            assert ingredient_row["days_remaining"] == 3

            with engine.begin() as connection:
                connection.execute(text("UPDATE production_coverage_reservations SET reserved_quantity=3 WHERE lot_id=:lot"), {"lot": produced_lot_id})
            rows = client.get("/api/dashboard/use-soon?days=7").json()["recommendations"]
            assert all(row["lot_id"] != produced_lot_id for row in rows)
        finally:
            with engine.begin() as connection:
                if produced_lot_id is not None:
                    connection.execute(text("DELETE FROM production_coverage_reservations WHERE lot_id=:lot"), {"lot": produced_lot_id})
                    connection.execute(text("DELETE FROM inventory_transactions WHERE lot_id=:lot"), {"lot": produced_lot_id})
                    connection.execute(text("DELETE FROM inventory_lots WHERE id=:lot"), {"lot": produced_lot_id})
                if ingredient_lot_id is not None:
                    connection.execute(text("DELETE FROM inventory_transactions WHERE lot_id=:lot"), {"lot": ingredient_lot_id})
                    connection.execute(text("DELETE FROM inventory_lots WHERE id=:lot"), {"lot": ingredient_lot_id})
                if cycle_id is not None:
                    connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle"), {"cycle": cycle_id})
                    connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle"), {"cycle": cycle_id})
                    connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": cycle_id})
                if ingredient_id is not None:
                    connection.execute(text("DELETE FROM ingredient_aliases WHERE ingredient_id=:ingredient"), {"ingredient": ingredient_id})
                    connection.execute(text("DELETE FROM ingredients WHERE id=:ingredient"), {"ingredient": ingredient_id})
