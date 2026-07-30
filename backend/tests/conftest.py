import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


@pytest.fixture
def app():
    settings = Settings(
        app_env="test",
        auth_mode="development",
        database_url="sqlite:///:memory:",
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.database.engine)
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev:test-owner"}


@pytest.fixture
def workspace(client, auth_headers):
    response = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Test workspace", "timezone": "Australia/Melbourne"},
    )
    assert response.status_code == 201
    return response.json()["data"]
