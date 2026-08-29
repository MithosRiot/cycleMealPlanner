from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app


def test_seeded_reference_data_and_safe_unit_conversion() -> None:
    with TestClient(app) as client:
        household = client.get("/api/reference/household")
        assert household.status_code == 200
        assert household.json()["default_servings"] == "4.000"

        units = client.get("/api/reference/units")
        assert units.status_code == 200
        codes = {unit["code"] for unit in units.json()}
        assert {"oz", "lb", "cup", "each", "dozen"}.issubset(codes)

        converted = client.post(
            "/api/reference/units/convert",
            json={"quantity": "2", "from_unit_code": "lb", "to_unit_code": "oz"},
        )
        assert converted.status_code == 200
        assert Decimal(converted.json()["quantity"]) == Decimal("32")

        unsafe = client.post(
            "/api/reference/units/convert",
            json={"quantity": "1", "from_unit_code": "cup", "to_unit_code": "oz"},
        )
        assert unsafe.status_code == 400


def test_locations_support_hierarchy_and_archive_rules() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/reference/inventory-locations",
            json={"name": "Kitchen", "location_type": "OTHER", "sort_order": 1},
        )
        assert created.status_code == 201
        parent_id = created.json()["id"]

        child = client.post(
            "/api/reference/inventory-locations",
            json={
                "name": "Baking Shelf",
                "parent_location_id": parent_id,
                "location_type": "PANTRY",
                "sort_order": 1,
            },
        )
        assert child.status_code == 201
        child_id = child.json()["id"]

        blocked = client.delete(f"/api/reference/inventory-locations/{parent_id}")
        assert blocked.status_code == 409

        archived_child = client.delete(f"/api/reference/inventory-locations/{child_id}")
        assert archived_child.status_code == 204
        archived_parent = client.delete(f"/api/reference/inventory-locations/{parent_id}")
        assert archived_parent.status_code == 204


def test_household_and_categories_are_editable() -> None:
    with TestClient(app) as client:
        household = client.put(
            "/api/reference/household",
            json={"name": "Test Household", "default_servings": "5"},
        )
        assert household.status_code == 200
        assert household.json()["name"] == "Test Household"

        category = client.post(
            "/api/reference/shopping-categories",
            json={"name": "Bulk Foods", "sort_order": 15},
        )
        assert category.status_code == 201
        category_id = category.json()["id"]

        updated = client.put(
            f"/api/reference/shopping-categories/{category_id}",
            json={"name": "Bulk", "sort_order": 16, "active": True},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Bulk"

        archived = client.delete(f"/api/reference/shopping-categories/{category_id}")
        assert archived.status_code == 204
