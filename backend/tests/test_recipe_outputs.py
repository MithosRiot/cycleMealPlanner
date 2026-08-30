from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _recipe(client: TestClient, name: str) -> dict:
    response = client.post("/api/recipes", json={
        "name": name, "description": None, "base_servings": "4", "serving_unit": "servings",
        "yield_quantity": None, "yield_unit_id": None, "prep_time_minutes": None, "cook_time_minutes": None,
        "notes": None, "favorite": False, "meal_types": [], "tag_ids": [], "prep_groups": [],
        "advance_prep": [], "equipment": [], "ingredients": [],
    })
    assert response.status_code == 201
    return response.json()


def test_outputs_dependencies_scale_and_persist() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {row["code"]: row["id"] for row in client.get("/api/reference/units").json()}
        source = _recipe(client, f"Stock Source {suffix}")
        consumer = _recipe(client, f"Soup Consumer {suffix}")

        output_response = client.post(f"/api/recipes/{source['id']}/outputs", json={
            "name": "Chicken stock", "quantity": "4", "unit_id": units["cup"], "notes": "Reusable stock", "active": True, "sort_order": 0,
        })
        assert output_response.status_code == 201
        output = output_response.json()

        dependency_response = client.post(f"/api/recipes/{consumer['id']}/dependencies", json={
            "recipe_output_id": output["id"], "quantity": "2", "unit_id": units["cup"], "scaling_mode": "LINEAR", "notes": None, "sort_order": 0,
        })
        assert dependency_response.status_code == 201

        bundle = client.get(f"/api/recipes/{consumer['id']}/outputs-dependencies").json()
        assert len(bundle["dependencies"]) == 1
        assert bundle["dependencies"][0]["recipe_output_id"] == output["id"]

        scaled = client.post(f"/api/recipes/{consumer['id']}/dependencies/scale", json={"requested_servings": "8"})
        assert scaled.status_code == 200
        row = scaled.json()["dependencies"][0]
        assert Decimal(row["quantity"]) == Decimal("4")
        assert row["output_name"] == "Chicken stock"
        assert row["manual_review"] is False

        reloaded = client.get(f"/api/recipes/{source['id']}/outputs-dependencies").json()
        assert reloaded["outputs"][0]["name"] == "Chicken stock"
        assert Decimal(reloaded["outputs"][0]["quantity"]) == Decimal("4")


def test_manual_dependency_and_validation() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {row["code"]: row["id"] for row in client.get("/api/reference/units").json()}
        source = _recipe(client, f"Manual Source {suffix}")
        consumer = _recipe(client, f"Manual Consumer {suffix}")
        output = client.post(f"/api/recipes/{source['id']}/outputs", json={"name": "Dough", "quantity": "1", "unit_id": units["each"], "notes": None, "active": True, "sort_order": 0}).json()

        self_output = client.post(f"/api/recipes/{consumer['id']}/outputs", json={"name": "Self output", "quantity": "1", "unit_id": units["each"], "notes": None, "active": True, "sort_order": 0}).json()
        self_dep = client.post(f"/api/recipes/{consumer['id']}/dependencies", json={"recipe_output_id": self_output["id"], "quantity": "1", "unit_id": units["each"], "scaling_mode": "LINEAR", "notes": None, "sort_order": 0})
        assert self_dep.status_code == 422

        incompatible = client.post(f"/api/recipes/{consumer['id']}/dependencies", json={"recipe_output_id": output["id"], "quantity": "1", "unit_id": units["cup"], "scaling_mode": "LINEAR", "notes": None, "sort_order": 0})
        assert incompatible.status_code == 422

        manual = client.post(f"/api/recipes/{consumer['id']}/dependencies", json={"recipe_output_id": output["id"], "quantity": "1", "unit_id": units["each"], "scaling_mode": "MANUAL", "notes": None, "sort_order": 0})
        assert manual.status_code == 201
        scaled = client.post(f"/api/recipes/{consumer['id']}/dependencies/scale", json={"requested_servings": "8"}).json()["dependencies"][0]
        assert scaled["manual_review"] is True
        assert Decimal(scaled["quantity"]) == Decimal("1")


def test_transitive_dependency_cycle_is_rejected() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        units = {row["code"]: row["id"] for row in client.get("/api/reference/units").json()}
        recipe_a = _recipe(client, f"Cycle A {suffix}")
        recipe_b = _recipe(client, f"Cycle B {suffix}")
        recipe_c = _recipe(client, f"Cycle C {suffix}")
        output_a = client.post(f"/api/recipes/{recipe_a['id']}/outputs", json={"name": "A output", "quantity": "1", "unit_id": units["each"], "notes": None, "active": True, "sort_order": 0}).json()
        output_b = client.post(f"/api/recipes/{recipe_b['id']}/outputs", json={"name": "B output", "quantity": "1", "unit_id": units["each"], "notes": None, "active": True, "sort_order": 0}).json()
        output_c = client.post(f"/api/recipes/{recipe_c['id']}/outputs", json={"name": "C output", "quantity": "1", "unit_id": units["each"], "notes": None, "active": True, "sort_order": 0}).json()

        assert client.post(f"/api/recipes/{recipe_a['id']}/dependencies", json={"recipe_output_id": output_b["id"], "quantity": "1", "unit_id": units["each"], "scaling_mode": "LINEAR", "notes": None, "sort_order": 0}).status_code == 201
        assert client.post(f"/api/recipes/{recipe_b['id']}/dependencies", json={"recipe_output_id": output_c["id"], "quantity": "1", "unit_id": units["each"], "scaling_mode": "LINEAR", "notes": None, "sort_order": 0}).status_code == 201
        cycle = client.post(f"/api/recipes/{recipe_c['id']}/dependencies", json={"recipe_output_id": output_a["id"], "quantity": "1", "unit_id": units["each"], "scaling_mode": "LINEAR", "notes": None, "sort_order": 0})
        assert cycle.status_code == 422
