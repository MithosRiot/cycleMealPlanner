from fastapi.testclient import TestClient

from app.main import app


def _reference_ids(client: TestClient) -> tuple[int, int, int]:
    category_id = client.get("/api/reference/shopping-categories").json()[0]["id"]
    unit_id = next(unit["id"] for unit in client.get("/api/reference/units").json() if unit["code"] == "lb")
    location_id = client.get("/api/reference/inventory-locations").json()[0]["id"]
    return category_id, unit_id, location_id


def test_ingredient_crud_alias_search_and_archive() -> None:
    with TestClient(app) as client:
        category_id, unit_id, location_id = _reference_ids(client)
        created = client.post(
            "/api/ingredients",
            json={
                "name": "Green Onion",
                "shopping_category_id": category_id,
                "preferred_unit_id": unit_id,
                "default_location_id": location_id,
                "perishable": True,
                "notes": "Keep refrigerated",
                "aliases": ["Scallion", "Spring Onion", "scallion"],
            },
        )
        assert created.status_code == 201
        ingredient = created.json()
        ingredient_id = ingredient["id"]
        assert ingredient["name"] == "Green Onion"
        assert {alias["alias"] for alias in ingredient["aliases"]} == {"Scallion", "Spring Onion"}

        searched = client.get("/api/ingredients", params={"search": "scallion"})
        assert searched.status_code == 200
        assert [item["id"] for item in searched.json()] == [ingredient_id]

        updated = client.put(
            f"/api/ingredients/{ingredient_id}",
            json={
                "name": "Green Onions",
                "shopping_category_id": category_id,
                "preferred_unit_id": unit_id,
                "default_location_id": location_id,
                "perishable": True,
                "notes": None,
                "aliases": ["Scallion"],
                "active": True,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Green Onions"

        archived = client.delete(f"/api/ingredients/{ingredient_id}")
        assert archived.status_code == 204
        active_list = client.get("/api/ingredients")
        assert ingredient_id not in {item["id"] for item in active_list.json()}
        all_list = client.get("/api/ingredients", params={"include_inactive": True})
        assert ingredient_id in {item["id"] for item in all_list.json()}


def test_ingredient_identity_prevents_name_alias_collisions() -> None:
    with TestClient(app) as client:
        first = client.post(
            "/api/ingredients",
            json={"name": "Cilantro", "aliases": ["Coriander Leaf"]},
        )
        assert first.status_code == 201

        duplicate_name = client.post("/api/ingredients", json={"name": " cilantro ", "aliases": []})
        assert duplicate_name.status_code == 409

        alias_as_name = client.post("/api/ingredients", json={"name": "Coriander Leaf", "aliases": []})
        assert alias_as_name.status_code == 409

        name_as_alias = client.post(
            "/api/ingredients",
            json={"name": "Fresh Herb", "aliases": ["Cilantro"]},
        )
        assert name_as_alias.status_code == 409


def test_tags_are_reusable_editable_and_archivable() -> None:
    with TestClient(app) as client:
        created = client.post("/api/tags", json={"name": "Mexican", "category": "Cuisine"})
        assert created.status_code == 201
        tag_id = created.json()["id"]
        assert created.json()["category"] == "CUISINE"

        duplicate = client.post("/api/tags", json={"name": " mexican ", "category": "Cuisine"})
        assert duplicate.status_code == 409

        updated = client.put(
            f"/api/tags/{tag_id}",
            json={"name": "Tex-Mex", "category": "Cuisine", "active": True},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Tex-Mex"

        archived = client.delete(f"/api/tags/{tag_id}")
        assert archived.status_code == 204
        active_tags = client.get("/api/tags").json()
        assert tag_id not in {tag["id"] for tag in active_tags}
