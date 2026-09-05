from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_direct_recipe_flows_through_planning_operations_completion_and_production() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = client.get("/api/reference/units").json()
        each = next(item for item in units if item["code"] == "each")
        refrigerator = next(item for item in client.get("/api/reference/inventory-locations").json() if item["name"] == "Refrigerator")

        ingredient = client.post("/api/ingredients", json={
            "name": f"Direct Recipe Ingredient {suffix}",
            "shopping_category_id": None,
            "preferred_unit_id": each["id"],
            "default_location_id": refrigerator["id"],
            "perishable": False,
            "notes": None,
            "aliases": [],
        }).json()
        lot_response = client.post("/api/inventory", json={
            "ingredient_id": ingredient["id"],
            "location_id": refrigerator["id"],
            "quantity": "8",
            "unit_id": each["id"],
            "purchase_date": None,
            "opened_date": None,
            "expiration_date": None,
            "frozen_date": None,
            "thawed_date": None,
            "notes": None,
            "transaction_type": "MANUAL_ADD",
        })
        assert lot_response.status_code == 201
        lot = lot_response.json()

        recipe_response = client.post("/api/recipes", json={
            "name": f"Direct Recipe {suffix}",
            "description": "Direct Recipe workflow regression",
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
            "advance_prep": [{
                "task_type": "PREP",
                "title": "Direct prep task",
                "lead_time_minutes": 30,
                "duration_minutes": 5,
                "instructions": "Prepare directly.",
                "reminder_enabled": False,
                "reminder_offset_minutes": None,
                "prep_group_key": None,
                "sort_order": 0,
            }],
            "equipment": [],
            "ingredients": [{
                "ingredient_id": ingredient["id"],
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
        assert recipe_response.status_code == 201
        recipe = recipe_response.json()

        cooking_response = client.put(f"/api/recipes/{recipe['id']}/cooking-steps", json=[{
            "title": "Cook direct Recipe",
            "instructions": "Cook it.",
            "prep_group_id": None,
            "sort_order": 0,
            "timers": [],
            "recipe_equipment_ids": [],
            "temperatures": [],
            "coordination_stage": 0,
            "parallel_capable": False,
            "depends_on_step_orders": [],
        }])
        assert cooking_response.status_code == 200

        cycle_response = client.post("/api/meal-cycles", json={
            "name": f"Direct Recipe Cycle {suffix}",
            "duration_days": 1,
            "start_date": "2026-09-10",
            "notes": None,
            "slot_definitions": [{"label": "Dinner", "sort_order": 0, "serving_time": "18:00:00"}],
        })
        assert cycle_response.status_code == 201
        cycle = cycle_response.json()
        slot = cycle["slots"][0]

        placed_response = client.post(
            f"/api/meal-cycles/{cycle['id']}/slots/{slot['id']}/planned-recipe",
            json={"recipe_id": recipe["id"], "planned_servings": "4", "planned_leftover_servings": "1"},
        )
        assert placed_response.status_code == 201
        planned = placed_response.json()
        assert planned["source_type"] == "DIRECT_RECIPE"
        assert planned["meal_id"] is None
        assert planned["source_recipe_id"] == recipe["id"]
        assert planned["snapshot_name"] == recipe["name"]
        scaled = __import__("json").loads(planned["scaled_components"])
        assert len(scaled) == 1
        assert scaled[0]["recipe_id"] == recipe["id"]
        assert scaled[0]["requested_servings"] == "5.000"
        assert scaled[0]["ingredients"][0]["quantity"] == "5.000000"

        reservations = client.post(f"/api/meal-cycles/{cycle['id']}/reservations/regenerate")
        assert reservations.status_code == 200
        reservation_body = reservations.json()
        assert reservation_body["active_count"] == 1
        assert reservation_body["reservations"][0]["planned_meal_id"] == planned["id"]
        assert reservation_body["reservations"][0]["quantity"] == "5.000000"

        shopping = client.post(f"/api/shopping/{cycle['id']}/regenerate")
        assert shopping.status_code == 200
        shopping_item = next(item for item in shopping.json()["items"] if item["ingredient_id"] == ingredient["id"])
        assert shopping_item["required_quantity"] == "5.000000"
        assert shopping_item["generated_quantity"] == "0.000000"

        prep = client.get(f"/api/meal-cycles/{cycle['id']}/prep-schedule")
        assert prep.status_code == 200
        prep_task = prep.json()["tasks"][0]
        assert prep_task["planned_meal_id"] == planned["id"]
        assert prep_task["meal_id"] is None
        assert prep_task["recipe_id"] == recipe["id"]
        assert prep_task["title"] == "Direct prep task"

        gather = client.get(f"/api/meal-cycles/{cycle['id']}/gather")
        assert gather.status_code == 200
        requirement = gather.json()["requirements"][0]
        assert requirement["planned_meal_id"] == planned["id"]
        assert requirement["recipe_id"] == recipe["id"]
        assert requirement["required_quantity"] == "5.000000"

        cooking = client.get(f"/api/meal-cycles/{cycle['id']}/cooking-mode")
        assert cooking.status_code == 200
        cooking_meal = cooking.json()["meals"][0]
        assert cooking_meal["planned_meal_id"] == planned["id"]
        assert cooking_meal["meal_name"] == recipe["name"]
        assert cooking_meal["steps"][0]["title"] == "Cook direct Recipe"

        draft = client.post(f"/api/planned-meals/{planned['id']}/completion")
        assert draft.status_code == 200
        assert draft.json()["usages"][0]["planned_quantity"] == "5.000000"
        finalized = client.post(f"/api/planned-meals/{planned['id']}/completion/finalize")
        assert finalized.status_code == 200
        assert finalized.json()["completion"]["status"] == "FINALIZED"
        assert client.get(f"/api/inventory/{lot['id']}").json()["quantity"] == "3.000000"

        preview = client.get(f"/api/planned-meals/{planned['id']}/completion/production-preview")
        assert preview.status_code == 200
        assert preview.json()["default_leftover_servings"] == "1.000"
        committed = client.post(f"/api/planned-meals/{planned['id']}/completion/production", json={
            "actual_servings_produced": "5",
            "actual_servings_eaten": "4",
            "leftover_location_id": refrigerator["id"],
            "leftover_expiration_date": "2026-09-12",
            "leftover_notes": "Direct Recipe leftover",
            "outputs": [],
        })
        assert committed.status_code == 200
        leftover = committed.json()["leftover"]
        assert leftover["source_meal_id"] is None
        assert leftover["source_recipe_id"] == recipe["id"]
        assert leftover["leftover_servings"] == "1.000"

        options = client.get("/api/produced-source-options")
        assert options.status_code == 200
        direct_leftover = next(row for row in options.json() if row["source_type"] == "LEFTOVER" and row["source_origin_planned_meal_id"] == planned["id"])
        assert direct_leftover["source_meal_id"] is None
        assert direct_leftover["available_quantity"] == "1.000000"
