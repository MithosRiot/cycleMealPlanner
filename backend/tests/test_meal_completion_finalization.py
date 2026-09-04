from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _ingredient(client: TestClient, name: str, unit_id: int, location_id: int) -> dict:
    return client.post("/api/ingredients", json={
        "name": name,
        "shopping_category_id": None,
        "preferred_unit_id": unit_id,
        "default_location_id": location_id,
        "perishable": False,
        "notes": None,
        "aliases": [],
    }).json()


def _lot(client: TestClient, ingredient_id: int, location_id: int, unit_id: int, quantity: str, expiration_date: str | None = None) -> dict:
    response = client.post("/api/inventory", json={
        "ingredient_id": ingredient_id,
        "location_id": location_id,
        "quantity": quantity,
        "unit_id": unit_id,
        "purchase_date": "2026-09-01",
        "opened_date": None,
        "expiration_date": expiration_date,
        "frozen_date": None,
        "thawed_date": None,
        "notes": None,
        "transaction_type": "MANUAL_ADD",
    })
    assert response.status_code == 201
    return response.json()


def test_finalize_consumes_actual_substitution_multilot_units_rolls_back_shortage_and_is_idempotent() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        each = units["each"]
        gram = units["g"]
        kilogram = units["kg"]
        location = client.get("/api/reference/inventory-locations").json()[0]

        onion = _ingredient(client, f"Finalize Onion {suffix}", each["id"], location["id"])
        shallot = _ingredient(client, f"Finalize Shallot {suffix}", each["id"], location["id"])
        flour = _ingredient(client, f"Finalize Flour {suffix}", gram["id"], location["id"])

        shallot_lot_1 = _lot(client, shallot["id"], location["id"], each["id"], "1", "2026-09-06")
        shallot_lot_2 = _lot(client, shallot["id"], location["id"], each["id"], "1", "2026-09-07")
        flour_kg_lot = _lot(client, flour["id"], location["id"], kilogram["id"], "0.5", "2026-09-06")
        flour_g_lot = _lot(client, flour["id"], location["id"], gram["id"], "300", "2026-09-07")

        recipe = client.post("/api/recipes", json={
            "name": f"Finalize Recipe {suffix}", "description": None, "base_servings": "4",
            "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
            "prep_time_minutes": 5, "cook_time_minutes": 10, "notes": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [], "prep_groups": [], "advance_prep": [], "equipment": [],
            "ingredients": [
                {
                    "ingredient_id": onion["id"], "prep_group_key": None, "quantity": "2", "unit_id": each["id"],
                    "display_text": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None,
                    "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None,
                    "substitutions": [{"substitute_ingredient_id": shallot["id"], "ratio": "1", "preferred": True, "notes": None, "sort_order": 0}],
                },
                {
                    "ingredient_id": flour["id"], "prep_group_key": None, "quantity": "700", "unit_id": gram["id"],
                    "display_text": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None,
                    "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 1, "notes": None,
                    "substitutions": [],
                },
            ],
        }).json()
        meal = client.post("/api/meals", json={
            "name": f"Finalize Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Finalize Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot = cycle["slots"][0]
        planned = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]}).json()

        assert client.post(f"/api/meal-cycles/{cycle['id']}/gather/apply-suggestions").status_code == 200
        draft = client.post(f"/api/planned-meals/{planned['id']}/completion").json()
        onion_usage = next(row for row in draft["usages"] if row["planned_ingredient_id"] == onion["id"])
        flour_usage = next(row for row in draft["usages"] if row["planned_ingredient_id"] == flour["id"])

        shortage_save = client.put(f"/api/planned-meals/{planned['id']}/completion", json={"usages": [
            {"usage_id": onion_usage["id"], "actual_ingredient_id": shallot["id"], "actual_quantity": "3", "actual_unit_id": each["id"], "notes": "substitute"},
            {"usage_id": flour_usage["id"], "actual_ingredient_id": flour["id"], "actual_quantity": "700", "actual_unit_id": gram["id"], "notes": None},
        ]})
        assert shortage_save.status_code == 200

        before = {lot_id: client.get(f"/api/inventory/{lot_id}").json() for lot_id in [shallot_lot_1["id"], shallot_lot_2["id"], flour_kg_lot["id"], flour_g_lot["id"]]}
        shortage = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
        assert shortage.status_code == 409
        detail = shortage.json()["detail"]
        assert detail["shortages"][0]["ingredient_id"] == shallot["id"]
        assert Decimal(detail["shortages"][0]["shortage_quantity"]) == Decimal("1")
        after_shortage = {lot_id: client.get(f"/api/inventory/{lot_id}").json() for lot_id in before}
        assert {lot_id: row["quantity"] for lot_id, row in after_shortage.items()} == {lot_id: row["quantity"] for lot_id, row in before.items()}
        assert client.get(f"/api/planned-meals/{planned['id']}/completion").json()["status"] == "DRAFT"

        saved = client.put(f"/api/planned-meals/{planned['id']}/completion", json={"usages": [
            {"usage_id": onion_usage["id"], "actual_ingredient_id": shallot["id"], "actual_quantity": "2", "actual_unit_id": each["id"], "notes": "substitute"},
            {"usage_id": flour_usage["id"], "actual_ingredient_id": flour["id"], "actual_quantity": "700", "actual_unit_id": gram["id"], "notes": None},
        ]})
        assert saved.status_code == 200

        finalized = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
        assert finalized.status_code == 200
        body = finalized.json()["completion"]
        assert body["status"] == "FINALIZED"
        assert body["finalized_at"] is not None
        onion_final = next(row for row in body["usages"] if row["id"] == onion_usage["id"])
        flour_final = next(row for row in body["usages"] if row["id"] == flour_usage["id"])
        assert onion_final["actual_ingredient_id"] == shallot["id"]
        assert len(onion_final["allocations"]) == 2
        assert sum(Decimal(row["quantity"]) for row in onion_final["allocations"]) == Decimal("2")
        assert sum(Decimal(row["quantity"]) for row in flour_final["allocations"]) == Decimal("700")
        assert {row["source_unit_code"] for row in flour_final["allocations"]} == {"kg", "g"}

        shallot_1 = client.get(f"/api/inventory/{shallot_lot_1['id']}").json()
        shallot_2 = client.get(f"/api/inventory/{shallot_lot_2['id']}").json()
        flour_kg = client.get(f"/api/inventory/{flour_kg_lot['id']}").json()
        flour_g = client.get(f"/api/inventory/{flour_g_lot['id']}").json()
        assert Decimal(shallot_1["quantity"]) == 0
        assert Decimal(shallot_2["quantity"]) == 0
        assert Decimal(flour_kg["quantity"]) == 0
        assert Decimal(flour_g["quantity"]) == Decimal("100")
        for row in [shallot_1, shallot_2, flour_kg, flour_g]:
            assert row["transactions"][-1]["transaction_type"] == "CONSUME"

        transaction_counts = {row["id"]: len(row["transactions"]) for row in [shallot_1, shallot_2, flour_kg, flour_g]}
        repeated = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
        assert repeated.status_code == 200
        assert repeated.json()["completion"]["status"] == "FINALIZED"
        for lot_id, count in transaction_counts.items():
            assert len(client.get(f"/api/inventory/{lot_id}").json()["transactions"]) == count

        edit_after = client.put(f"/api/planned-meals/{planned['id']}/completion", json={"usages": []})
        assert edit_after.status_code == 409
