from fastapi.testclient import TestClient

from app.main import app


def _recipe_payload(name: str, equipment: list[dict]) -> dict:
    return {
        "name": name,
        "description": None,
        "base_servings": "4",
        "serving_unit": "servings",
        "yield_quantity": None,
        "yield_unit_id": None,
        "prep_time_minutes": None,
        "cook_time_minutes": None,
        "notes": None,
        "favorite": False,
        "meal_types": [],
        "tag_ids": [],
        "prep_groups": [],
        "advance_prep": [],
        "equipment": equipment,
        "ingredients": [],
    }


def test_equipment_crud_and_recipe_requirements() -> None:
    with TestClient(app) as client:
        skillet = client.post("/api/equipment", json={"name": "Equipment Test Skillet", "category": "cookware", "notes": "12 inch"})
        assert skillet.status_code == 201
        skillet_id = skillet.json()["id"]
        assert skillet.json()["category"] == "COOKWARE"

        blender = client.post("/api/equipment", json={"name": "Equipment Test Blender", "category": "appliance", "notes": None})
        assert blender.status_code == 201
        blender_id = blender.json()["id"]

        duplicate = client.post("/api/equipment", json={"name": " equipment test skillet ", "category": "OTHER", "notes": None})
        assert duplicate.status_code == 409

        created = client.post(
            "/api/recipes",
            json=_recipe_payload(
                "Equipment Requirement Recipe",
                [
                    {"equipment_id": skillet_id, "quantity": 2, "notes": "One large, one small", "sort_order": 1},
                    {"equipment_id": blender_id, "quantity": 1, "notes": None, "sort_order": 0},
                ],
            ),
        )
        assert created.status_code == 201
        recipe = created.json()
        assert [item["equipment_id"] for item in recipe["equipment"]] == [blender_id, skillet_id]
        assert recipe["equipment"][1]["quantity"] == 2

        scaled = client.post(f"/api/recipes/{recipe['id']}/scale", json={"requested_servings": "8", "unit_overrides": {}})
        assert scaled.status_code == 200
        reloaded = client.get(f"/api/recipes/{recipe['id']}").json()
        assert reloaded["equipment"] == recipe["equipment"]

        archived = client.delete(f"/api/equipment/{blender_id}")
        assert archived.status_code == 204
        active_ids = {item["id"] for item in client.get("/api/equipment").json()}
        assert blender_id not in active_ids
        all_ids = {item["id"] for item in client.get("/api/equipment", params={"include_inactive": True}).json()}
        assert blender_id in all_ids

        new_recipe_with_archived = client.post(
            "/api/recipes",
            json=_recipe_payload("Archived Equipment Recipe", [{"equipment_id": blender_id, "quantity": 1, "notes": None, "sort_order": 0}]),
        )
        assert new_recipe_with_archived.status_code == 400


def test_legacy_recipe_without_equipment_is_compatible() -> None:
    with TestClient(app) as client:
        created = client.post("/api/recipes", json=_recipe_payload("Legacy No Equipment Recipe", []))
        assert created.status_code == 201
        assert created.json()["equipment"] == []
