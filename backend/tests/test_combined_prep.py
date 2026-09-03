from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _recipe_payload(name: str, ingredient_id: int, unit_id: int, quantity: str, method: str, size: str, task_title: str) -> dict:
    return {
        "name": name,
        "description": None,
        "base_servings": "4",
        "serving_unit": "servings",
        "yield_quantity": None,
        "yield_unit_id": None,
        "prep_time_minutes": 10,
        "cook_time_minutes": 20,
        "notes": None,
        "favorite": False,
        "meal_types": ["DINNER"],
        "tag_ids": [],
        "prep_groups": [{"client_key": "main", "name": "Main prep", "sort_order": 0}],
        "advance_prep": [{
            "task_type": "PREP", "title": task_title, "lead_time_minutes": 30,
            "duration_minutes": 5, "instructions": "Prepare together", "prep_group_key": "main",
            "reminder_enabled": True, "reminder_offset_minutes": 10, "sort_order": 0,
        }],
        "equipment": [],
        "ingredients": [{
            "ingredient_id": ingredient_id, "prep_group_key": "main", "quantity": quantity,
            "unit_id": unit_id, "preparation": "Prepare as directed", "prep_method": method,
            "prep_size": size, "prep_state": "fresh", "optional": False,
            "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0,
            "notes": None, "substitutions": [],
        }],
    }


def test_combines_matching_component_prep_and_keeps_incompatible_prep_separate() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item for item in client.get("/api/reference/units").json()}
        location = client.get("/api/reference/inventory-locations").json()[0]
        ingredient = client.post("/api/ingredients", json={
            "name": f"Combined Prep Onion {suffix}", "shopping_category_id": None,
            "preferred_unit_id": units["each"]["id"], "default_location_id": location["id"],
            "perishable": False, "notes": None, "aliases": [],
        }).json()

        first = client.post("/api/recipes", json=_recipe_payload(
            f"Combined Prep A {suffix}", ingredient["id"], units["each"]["id"], "1", "CHOP", "diced", "Prep aromatics"
        )).json()
        second = client.post("/api/recipes", json=_recipe_payload(
            f"Combined Prep B {suffix}", ingredient["id"], units["each"]["id"], "2", "CHOP", "diced", "Prep aromatics"
        )).json()
        third = client.post("/api/recipes", json=_recipe_payload(
            f"Combined Prep C {suffix}", ingredient["id"], units["each"]["id"], "1", "SLICE", "thin", "Slice garnish"
        )).json()

        meal = client.post("/api/meals", json={
            "name": f"Combined Prep Meal {suffix}", "description": None, "favorite": False,
            "meal_types": ["DINNER"], "tag_ids": [],
            "recipes": [
                {"recipe_id": first["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 0, "notes": None},
                {"recipe_id": second["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 1, "notes": None},
                {"recipe_id": third["id"], "serving_multiplier": "1", "default_servings": "4", "sort_order": 2, "notes": None},
            ],
        }).json()
        cycle = client.post("/api/meal-cycles", json={
            "name": f"Combined Prep Cycle {suffix}", "duration_days": 1, "start_date": "2026-09-05", "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        }).json()
        slot_id = cycle["slots"][0]["id"]
        placed = client.post(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal", json={"meal_id": meal["id"]})
        assert placed.status_code == 201

        response = client.get(f"/api/meal-cycles/{cycle['id']}/combined-prep")
        assert response.status_code == 200
        body = response.json()

        chopped = [row for row in body["ingredient_prep"] if row["prep_method"] == "CHOP"]
        sliced = [row for row in body["ingredient_prep"] if row["prep_method"] == "SLICE"]
        assert len(chopped) == 1
        assert Decimal(chopped[0]["quantity"]) == Decimal("3")
        assert len(chopped[0]["sources"]) == 2
        assert len(sliced) == 1
        assert Decimal(sliced[0]["quantity"]) == Decimal("1")

        combined_task = [row for row in body["advance_prep"] if row["title"] == "Prep aromatics"]
        separate_task = [row for row in body["advance_prep"] if row["title"] == "Slice garnish"]
        assert len(combined_task) == 1
        assert len(combined_task[0]["sources"]) == 2
        assert combined_task[0]["start_datetime"].startswith("2026-09-05T17:30")
        assert combined_task[0]["reminder_at"].startswith("2026-09-05T17:20")
        assert len(separate_task) == 1

        updated = client.put(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal/planning", json={
            "planned_servings": "8", "planned_leftover_servings": "0", "component_serving_overrides": {},
        })
        assert updated.status_code == 200
        changed = client.get(f"/api/meal-cycles/{cycle['id']}/combined-prep").json()
        changed_chopped = [row for row in changed["ingredient_prep"] if row["prep_method"] == "CHOP"][0]
        assert Decimal(changed_chopped["quantity"]) == Decimal("6")

        removed = client.delete(f"/api/meal-cycles/{cycle['id']}/slots/{slot_id}/planned-meal")
        assert removed.status_code == 204
        empty = client.get(f"/api/meal-cycles/{cycle['id']}/combined-prep").json()
        assert empty["ingredient_prep"] == []
        assert empty["advance_prep"] == []
