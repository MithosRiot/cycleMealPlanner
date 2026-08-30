from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _ingredient(client: TestClient, name: str, unit_id: int) -> dict:
    response = client.post(
        "/api/ingredients",
        json={"name": name, "shopping_category_id": None, "preferred_unit_id": unit_id, "default_location_id": None, "perishable": False, "notes": None, "aliases": []},
    )
    assert response.status_code == 201
    return response.json()


def _recipe_payload(name: str, canonical_id: int, unit_id: int, substitutions: list[dict], scaling_mode: str = "LINEAR") -> dict:
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
        "equipment": [],
        "ingredients": [{
            "ingredient_id": canonical_id,
            "prep_group_key": None,
            "quantity": "2",
            "unit_id": unit_id,
            "display_text": None,
            "preparation": None,
            "prep_method": None,
            "prep_size": None,
            "prep_state": None,
            "optional": False,
            "scaling_mode": scaling_mode,
            "required_state": "ANY",
            "sort_order": 0,
            "notes": None,
            "substitutions": substitutions,
        }],
    }


def test_recipe_substitutions_round_trip_and_per_use_scale() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        canonical = _ingredient(client, f"Canonical Flour {suffix}", units["cup"])
        almond = _ingredient(client, f"Almond Flour {suffix}", units["cup"])
        oat = _ingredient(client, f"Oat Flour {suffix}", units["cup"])

        created = client.post(
            "/api/recipes",
            json=_recipe_payload(
                f"Substitution Recipe {suffix}",
                canonical["id"],
                units["cup"],
                [
                    {"substitute_ingredient_id": almond["id"], "ratio": "1.25", "preferred": True, "notes": "Preferred", "sort_order": 0},
                    {"substitute_ingredient_id": oat["id"], "ratio": "0.5", "preferred": False, "notes": None, "sort_order": 1},
                ],
            ),
        )
        assert created.status_code == 201
        recipe = created.json()
        row = recipe["ingredients"][0]
        assert [sub["substitute_ingredient_id"] for sub in row["substitutions"]] == [almond["id"], oat["id"]]
        assert row["substitutions"][0]["preferred"] is True

        preferred_scale = client.post(
            f"/api/recipes/{recipe['id']}/scale",
            json={"requested_servings": "8", "unit_overrides": {}, "substitution_overrides": {}},
        )
        assert preferred_scale.status_code == 200
        preferred = preferred_scale.json()["ingredients"][0]
        assert preferred["canonical_ingredient_id"] == canonical["id"]
        assert preferred["ingredient_id"] == almond["id"]
        assert preferred["substitution_id"] == row["substitutions"][0]["id"]
        assert Decimal(preferred["quantity"]) == Decimal("5")

        oat_scale = client.post(
            f"/api/recipes/{recipe['id']}/scale",
            json={"requested_servings": "8", "unit_overrides": {}, "substitution_overrides": {str(row["id"]): row["substitutions"][1]["id"]}},
        )
        assert oat_scale.status_code == 200
        oat_result = oat_scale.json()["ingredients"][0]
        assert oat_result["ingredient_id"] == oat["id"]
        assert Decimal(oat_result["quantity"]) == Decimal("2")

        reloaded = client.get(f"/api/recipes/{recipe['id']}")
        assert reloaded.status_code == 200
        assert reloaded.json()["ingredients"][0]["substitutions"] == row["substitutions"]


def test_substitution_validation_and_manual_review() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        canonical = _ingredient(client, f"Manual Canonical {suffix}", units["each"])
        alternate = _ingredient(client, f"Manual Alternate {suffix}", units["each"])

        self_sub = client.post(
            "/api/recipes",
            json=_recipe_payload(f"Self Substitute {suffix}", canonical["id"], units["each"], [{"substitute_ingredient_id": canonical["id"], "ratio": "1", "preferred": False, "notes": None, "sort_order": 0}]),
        )
        assert self_sub.status_code == 422

        duplicate = client.post(
            "/api/recipes",
            json=_recipe_payload(f"Duplicate Substitute {suffix}", canonical["id"], units["each"], [
                {"substitute_ingredient_id": alternate["id"], "ratio": "1", "preferred": False, "notes": None, "sort_order": 0},
                {"substitute_ingredient_id": alternate["id"], "ratio": "2", "preferred": True, "notes": None, "sort_order": 1},
            ]),
        )
        assert duplicate.status_code == 422

        manual = client.post(
            "/api/recipes",
            json=_recipe_payload(f"Manual Substitute {suffix}", canonical["id"], units["each"], [{"substitute_ingredient_id": alternate["id"], "ratio": "2", "preferred": True, "notes": None, "sort_order": 0}], scaling_mode="MANUAL"),
        )
        assert manual.status_code == 201
        scaled = client.post(f"/api/recipes/{manual.json()['id']}/scale", json={"requested_servings": "8", "unit_overrides": {}, "substitution_overrides": {}})
        assert scaled.status_code == 200
        assert scaled.json()["ingredients"][0]["manual_review"] is True


def test_legacy_recipe_without_substitutions_is_compatible() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {item["code"]: item["id"] for item in client.get("/api/reference/units").json()}
        canonical = _ingredient(client, f"Legacy Substitute Ingredient {suffix}", units["each"])
        payload = _recipe_payload(f"Legacy Substitute Recipe {suffix}", canonical["id"], units["each"], [])
        payload["ingredients"][0].pop("substitutions")
        created = client.post("/api/recipes", json=payload)
        assert created.status_code == 201
        assert created.json()["ingredients"][0]["substitutions"] == []
