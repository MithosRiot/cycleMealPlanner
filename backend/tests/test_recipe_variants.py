from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _ingredient(client: TestClient, name: str, unit_id: int) -> dict:
    response = client.post("/api/ingredients", json={"name": name, "shopping_category_id": None, "preferred_unit_id": unit_id, "default_location_id": None, "perishable": False, "notes": None, "aliases": []})
    assert response.status_code == 201
    return response.json()


def test_recipe_variant_scaling_and_recipe_edit_remap() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        flour = _ingredient(client, f"Variant Flour {suffix}", units["cup"])
        almond = _ingredient(client, f"Variant Almond {suffix}", units["cup"])
        salt = _ingredient(client, f"Variant Salt {suffix}", units["tsp"])
        recipe_payload = {
            "name": f"Variant Recipe {suffix}", "description": None, "base_servings": "4", "serving_unit": "servings",
            "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": None, "cook_time_minutes": None,
            "notes": None, "favorite": False, "meal_types": [], "tag_ids": [], "prep_groups": [], "advance_prep": [], "equipment": [],
            "ingredients": [
                {"ingredient_id": flour["id"], "prep_group_key": None, "quantity": "2", "unit_id": units["cup"], "display_text": None, "preparation": None, "prep_method": "mix", "prep_size": None, "prep_state": None, "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "notes": None, "substitutions": [{"substitute_ingredient_id": almond["id"], "ratio": "1.25", "preferred": False, "notes": None, "sort_order": 0}]},
                {"ingredient_id": salt["id"], "prep_group_key": None, "quantity": "1", "unit_id": units["tsp"], "display_text": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None, "optional": False, "scaling_mode": "FIXED", "required_state": "ANY", "sort_order": 1, "notes": None, "substitutions": []},
            ],
        }
        created = client.post("/api/recipes", json=recipe_payload)
        assert created.status_code == 201
        recipe = created.json()
        flour_row = recipe["ingredients"][0]
        substitution_id = flour_row["substitutions"][0]["id"]

        variant_payload = {
            "name": "Almond Batch", "notes": "Test variant", "active": True, "sort_order": 0,
            "overrides": [{"recipe_ingredient_id": flour_row["id"], "quantity": "3", "unit_id": None, "substitution_id": substitution_id, "preparation": None, "prep_method": "whisk", "prep_size": None, "prep_state": None, "notes": None}],
        }
        variant = client.post(f"/api/recipes/{recipe['id']}/variants", json=variant_payload)
        assert variant.status_code == 201
        variant_id = variant.json()["id"]

        duplicate = client.post(f"/api/recipes/{recipe['id']}/variants", json={**variant_payload, "name": " almond batch "})
        assert duplicate.status_code == 409

        scaled = client.post(f"/api/recipes/{recipe['id']}/scale", json={"requested_servings": "8", "unit_overrides": {}, "substitution_overrides": {}, "variant_id": variant_id})
        assert scaled.status_code == 200
        body = scaled.json()
        assert body["variant_id"] == variant_id
        first = body["ingredients"][0]
        assert first["ingredient_id"] == almond["id"]
        assert Decimal(first["quantity"]) == Decimal("7.5")
        assert first["prep_method"] == "whisk"
        assert Decimal(body["ingredients"][1]["quantity"]) == Decimal("1")

        updated_payload = {**recipe_payload, "description": "Edited base", "active": True}
        updated_payload["ingredients"] = [dict(item) for item in recipe_payload["ingredients"]]
        updated_payload["ingredients"][0]["quantity"] = "4"
        edited = client.put(f"/api/recipes/{recipe['id']}", json=updated_payload)
        assert edited.status_code == 200
        remapped = client.get(f"/api/recipes/{recipe['id']}/variants").json()[0]
        assert len(remapped["overrides"]) == 1
        assert remapped["overrides"][0]["recipe_ingredient_id"] == edited.json()["ingredients"][0]["id"]
        assert remapped["overrides"][0]["substitution_id"] == edited.json()["ingredients"][0]["substitutions"][0]["id"]

        without_flour = {**updated_payload, "ingredients": [updated_payload["ingredients"][1]]}
        removed = client.put(f"/api/recipes/{recipe['id']}", json=without_flour)
        assert removed.status_code == 200
        after_remove = client.get(f"/api/recipes/{recipe['id']}/variants").json()[0]
        assert after_remove["overrides"] == []


def test_variant_rejects_foreign_override_and_bad_substitution() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        first = _ingredient(client, f"Variant One {suffix}", units["each"])
        second = _ingredient(client, f"Variant Two {suffix}", units["each"])
        def recipe(name: str, ingredient_id: int):
            return client.post("/api/recipes", json={"name": name, "description": None, "base_servings": "1", "serving_unit": "servings", "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": None, "cook_time_minutes": None, "notes": None, "favorite": False, "meal_types": [], "tag_ids": [], "prep_groups": [], "advance_prep": [], "equipment": [], "ingredients": [{"ingredient_id": ingredient_id, "quantity": "1", "unit_id": units["each"], "optional": False, "scaling_mode": "LINEAR", "required_state": "ANY", "sort_order": 0, "substitutions": []}]})
        recipe_a = recipe(f"Variant A {suffix}", first["id"]).json()
        recipe_b = recipe(f"Variant B {suffix}", second["id"]).json()
        foreign = client.post(f"/api/recipes/{recipe_a['id']}/variants", json={"name": "Bad", "notes": None, "active": True, "sort_order": 0, "overrides": [{"recipe_ingredient_id": recipe_b["ingredients"][0]["id"], "quantity": "2", "unit_id": None, "substitution_id": None, "preparation": None, "prep_method": None, "prep_size": None, "prep_state": None, "notes": None}]})
        assert foreign.status_code == 422
