from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.session import engine
from app.main import app


def _create_valid_cycle(client: TestClient, name: str) -> tuple[dict, int]:
    created = client.post(
        "/api/meal-cycles",
        json={
            "name": name,
            "duration_days": 1,
            "start_date": "2026-09-10",
            "notes": None,
            "slot_definitions": [
                {"label": "Dinner", "sort_order": 0, "serving_time": "18:30:00"},
            ],
        },
    )
    assert created.status_code == 201
    cycle = created.json()
    slot_id = cycle["slots"][0]["id"]
    suffix = uuid4().hex[:8]
    with engine.begin() as connection:
        meal_id = connection.execute(
            text("""
                INSERT INTO meals (household_id, name, normalized_name, description, favorite, active)
                VALUES (1, :name, :normalized, NULL, 0, 1)
                RETURNING id
            """),
            {"name": f"Lifecycle Meal {suffix}", "normalized": f"lifecycle meal {suffix}"},
        ).scalar_one()
        planned_id = connection.execute(
            text("""
                INSERT INTO planned_meals
                (cycle_slot_id, meal_id, locked, planned_servings, planned_leftover_servings,
                 component_serving_overrides, scaled_components, snapshot_name, snapshot_description,
                 snapshot_meal_types, snapshot_components)
                VALUES (:slot_id, :meal_id, 0, 4, 0, '{}', '[]', :name, NULL, '[]', '[]')
                RETURNING id
            """),
            {"slot_id": slot_id, "meal_id": meal_id, "name": f"Lifecycle Meal {suffix}"},
        ).scalar_one()
    return cycle, int(planned_id)


def test_activation_is_atomic_idempotent_and_only_one_cycle_can_be_active() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        first, _ = _create_valid_cycle(client, f"Lifecycle Active A {suffix}")
        second, _ = _create_valid_cycle(client, f"Lifecycle Active B {suffix}")

        activated = client.post(f"/api/meal-cycles/{first['id']}/activate")
        assert activated.status_code == 200
        body = activated.json()
        assert body["status"] == "ACTIVE"
        assert body["activated_at"] is not None

        repeated = client.post(f"/api/meal-cycles/{first['id']}/activate")
        assert repeated.status_code == 200
        assert repeated.json()["activated_at"] == body["activated_at"]

        blocked = client.post(f"/api/meal-cycles/{second['id']}/activate")
        assert blocked.status_code == 409
        assert "already ACTIVE" in blocked.json()["detail"]

        edit_blocked = client.put(
            f"/api/meal-cycles/{first['id']}/schedule",
            json={"start_date": "2026-09-11", "serving_times": {}},
        )
        assert edit_blocked.status_code == 409

        cancelled = client.post(f"/api/meal-cycles/{first['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"

        second_activated = client.post(f"/api/meal-cycles/{second['id']}/activate")
        assert second_activated.status_code == 200
        assert second_activated.json()["status"] == "ACTIVE"
        client.post(f"/api/meal-cycles/{second['id']}/cancel")


def test_cancel_releases_ingredient_and_produced_coverage_reservations() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle, planned_id = _create_valid_cycle(client, f"Lifecycle Release {suffix}")
        activated = client.post(f"/api/meal-cycles/{cycle['id']}/activate")
        assert activated.status_code == 200

        with engine.begin() as connection:
            unit_id = connection.execute(text("SELECT id FROM measurement_units ORDER BY id LIMIT 1")).scalar_one()
            ingredient_id = connection.execute(
                text("""
                    INSERT INTO ingredients (household_id, name, normalized_name, perishable, active, notes)
                    VALUES (1, :name, :normalized, 0, 1, NULL)
                    RETURNING id
                """),
                {"name": f"Lifecycle Ingredient {suffix}", "normalized": f"lifecycle ingredient {suffix}"},
            ).scalar_one()
            recipe_id = connection.execute(
                text("""
                    INSERT INTO recipes
                    (household_id, name, normalized_name, description, base_servings, serving_unit,
                     prep_time_minutes, cook_time_minutes, notes, favorite, active)
                    VALUES (1, :name, :normalized, NULL, 4, 'servings', NULL, NULL, NULL, 0, 1)
                    RETURNING id
                """),
                {"name": f"Lifecycle Recipe {suffix}", "normalized": f"lifecycle recipe {suffix}"},
            ).scalar_one()
            connection.execute(
                text("""
                    INSERT INTO inventory_reservations
                    (household_id, cycle_id, planned_meal_id, meal_recipe_id, recipe_id,
                     recipe_ingredient_id, ingredient_id, quantity, unit_id, status)
                    VALUES (1, :cycle_id, :planned_id, NULL, :recipe_id, NULL, :ingredient_id, 1, :unit_id, 'ACTIVE')
                """),
                {"cycle_id": cycle["id"], "planned_id": planned_id, "recipe_id": recipe_id, "ingredient_id": ingredient_id, "unit_id": unit_id},
            )
            connection.execute(
                text("""
                    INSERT INTO production_coverage_reservations
                    (household_id, cycle_id, planned_meal_id, cycle_slot_id,
                     source_origin_planned_meal_id, source_type, source_record_id,
                     source_recipe_output_id, lot_id, requested_quantity, reserved_quantity,
                     shortage_quantity, unit_id, status, release_reason, created_at, updated_at, released_at)
                    VALUES
                    (1, :cycle_id, :planned_id, :slot_id, :planned_id, 'LEFTOVER', NULL,
                     NULL, NULL, 1, 0, 1, :unit_id, 'ACTIVE', NULL, :now, :now, NULL)
                """),
                {"cycle_id": cycle["id"], "planned_id": planned_id, "slot_id": cycle["slots"][0]["id"], "unit_id": unit_id, "now": datetime.utcnow()},
            )

        cancelled = client.post(f"/api/meal-cycles/{cycle['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"
        assert cancelled.json()["cancelled_at"] is not None

        with engine.connect() as connection:
            ingredient_status = connection.execute(
                text("SELECT status FROM inventory_reservations WHERE cycle_id=:cycle_id ORDER BY id DESC LIMIT 1"),
                {"cycle_id": cycle["id"]},
            ).scalar_one()
            coverage = connection.execute(
                text("SELECT status, release_reason, released_at FROM production_coverage_reservations WHERE cycle_id=:cycle_id ORDER BY id DESC LIMIT 1"),
                {"cycle_id": cycle["id"]},
            ).one()
        assert ingredient_status == "RELEASED"
        assert coverage.status == "RELEASED"
        assert coverage.release_reason == "CYCLE_CANCELLED"
        assert coverage.released_at is not None


def test_completion_requires_all_planned_meals_finalized_and_is_idempotent() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        cycle, planned_id = _create_valid_cycle(client, f"Lifecycle Complete {suffix}")
        assert client.post(f"/api/meal-cycles/{cycle['id']}/activate").status_code == 200

        blocked = client.post(f"/api/meal-cycles/{cycle['id']}/complete")
        assert blocked.status_code == 409
        assert "not finalized" in blocked.json()["detail"]

        with engine.begin() as connection:
            now = datetime.utcnow()
            connection.execute(
                text("""
                    INSERT INTO meal_completions
                    (planned_meal_id, status, plan_fingerprint, snapshot_name,
                     snapshot_planned_servings, snapshot_planned_leftover_servings,
                     snapshot_scaled_components, created_at, updated_at, finalized_at)
                    VALUES (:planned_id, 'FINALIZED', :fingerprint, 'Lifecycle Meal', 4, 0, '[]', :now, :now, :now)
                """),
                {"planned_id": planned_id, "fingerprint": "a" * 64, "now": now},
            )

        completed = client.post(f"/api/meal-cycles/{cycle['id']}/complete")
        assert completed.status_code == 200
        body = completed.json()
        assert body["status"] == "COMPLETED"
        assert body["completed_at"] is not None

        repeated = client.post(f"/api/meal-cycles/{cycle['id']}/complete")
        assert repeated.status_code == 200
        assert repeated.json()["completed_at"] == body["completed_at"]

        cancelled = client.post(f"/api/meal-cycles/{cycle['id']}/cancel")
        assert cancelled.status_code == 409
