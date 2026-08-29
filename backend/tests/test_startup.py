from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database.session import engine


def test_health_endpoint_and_migrations() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    with engine.connect() as connection:
        migration_version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert migration_version == "0002_core_reference_data"


def test_sqlite_foreign_keys_and_wal_are_enabled() -> None:
    with TestClient(app):
        with engine.connect() as connection:
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()

    assert foreign_keys == 1
    assert str(journal_mode).lower() == "wal"
