from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_completion_draft_persists_actual_usage_substitution_and_stale_plan() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        each = next(item for item in units if item["code"] == "each")
        gram = next(item for item in units if item["code"] == "g")
        location = client.get("/api/reference/inventory-locations").json()[0]

        onion = client.post("/api/ingredients", json={
            "name": f"Completion Onion {suffix}", "shopping_category_id": None,
            "preferred_unit_id": each["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        shallot = client.post("/api/ingredients", json={
            "name": f"Completion Shallot {suffix}", "shopping_category_id": None,
            "preferred_unit_id": each["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()
        recipe = client.post("/api/recipes", json={
            "name": f"Completion Recipe {suffix}", "description": None, "base_servings": "4",
            "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None,
            "prep_time_minutes": 5, "cook_time_minutes": 10, "notes": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [], "prep_groups": [], "advance_prep": [], "equipment": [],
            "ingredients": [{
                "ingredient_id": onion["id"], "prep_group_key": None, "quantity": "2", "unit_id": each["id"],
                "display_text": None, "preparation": "diced", "prep_method": "CHOP", "prep_size": "small", "prep_state": "fresh",
                "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None,
                "substitutions": [{"substitute_ingredient_id": shallot["id"], "ratio": "1", "preferred": True, "notes": "Use if needed", "sort_order": 0}],
            }],
        }).json()
        meal = client.post("/api/meals", json={
            "name": f"Completion Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [],
            "recipes": [{"recipe_id": recipe["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None}],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Completion Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot = cycle["slots"][0]
        planned = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal", json={"meal_id": meal["id"]}).json()

        inventory_before = client.get("/api/inventory").json()
        started = client.post(f"/api/planned-meals/{planned['id']}/completion")
        assert started.status_code == 200
        draft = started.json()
        assert draft["status"] == "DRAFT"
        assert draft["stale"] is False
        assert len(draft["usages"]) == 1
        usage = draft["usages"][0]
        assert usage["planned_ingredient_id"] == onion["id"]
        assert usage["actual_ingredient_id"] == onion["id"]
        assert Decimal(usage["actual_quantity"]) == Decimal("2")
        assert usage["substitutions"][0]["ingredient_id"] == shallot["id"]
        assert usage["substitutions"][0]["preferred"] is True

        incompatible = client.put(f"/api/planned-meals/{planned['id']}/completion", json={"usages": [{
            "usage_id": usage["id"], "actual_ingredient_id": shallot["id"], "actual_quantity": "1.5",
            "actual_unit_id": gram["id"], "notes": None,
        }]})
        assert incompatible.status_code == 422

        saved = client.put(f"/api/planned-meals/{planned['id']}/completion", json={"usages": [{
            "usage_id": usage["id"], "actual_ingredient_id": shallot["id"], "actual_quantity": "1.5",
            "actual_unit_id": each["id"], "notes": "Used shallots instead",
        }]})
        assert saved.status_code == 200
        changed = saved.json()["usages"][0]
        assert changed["planned_ingredient_id"] == onion["id"]
        assert changed["actual_ingredient_id"] == shallot["id"]
        assert Decimal(changed["actual_quantity"]) == Decimal("1.5")

        reopened = client.post(f"/api/planned-meals/{planned['id']}/completion").json()
        assert reopened["id"] == draft["id"]
        assert reopened["usages"][0]["actual_ingredient_id"] == shallot["id"]
        assert Decimal(reopened["usages"][0]["actual_quantity"]) == Decimal("1.5")
        assert client.get("/api/inventory").json() == inventory_before

        planning = client.put(f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-meal/planning", json={
            "planned_servings": "8", "planned_leftover_servings": "0", "component_serving_overrides": {},
        })
        assert planning.status_code == 200
        stale = client.get(f"/api/planned-meals/{planned['id']}/completion").json()
        assert stale["stale"] is True
        assert Decimal(stale["usages"][0]["actual_quantity"]) == Decimal("1.5")

        refreshed = client.post(f"/api/planned-meals/{planned['id']}/completion/refresh")
        assert refreshed.status_code == 200
        refreshed_body = refreshed.json()
        assert refreshed_body["stale"] is False
        assert Decimal(refreshed_body["usages"][0]["planned_quantity"]) == Decimal("4")
        assert Decimal(refreshed_body["usages"][0]["actual_quantity"]) == Decimal("1.5")
        assert refreshed_body["usages"][0]["actual_ingredient_id"] == shallot["id"]
        assert client.get("/api/inventory").json() == inventory_before
