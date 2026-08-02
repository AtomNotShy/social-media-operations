from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


def test_metrics_records_route_template(client):
    assert client.get("/health/live").status_code == 200

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "social_ops_http_requests_total" in response.text
    assert 'method="GET",route="/health/live",status_code="200"' in response.text
    assert 'route="/metrics"' not in response.text
    assert "social_ops_database_metrics_collection_success 1.0" in response.text


def test_database_metrics_use_bounded_labels_without_workspace_ids(
    client,
    auth_headers,
    workspace,
):
    headers = {**auth_headers, "X-Workspace-Id": workspace["id"]}
    profile = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": "metrics-profile",
            "profile_url": "https://www.xiaohongshu.com/user/profile/metrics-profile",
            "display_name": "Metrics profile",
        },
    ).json()["data"]
    client.post(
        f"/api/v1/tracked-profiles/{profile['id']}/sync",
        headers=headers,
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert 'social_ops_jobs{job_type="PROFILE_SCAN",status="pending"} 1.0' in response.text
    assert 'social_ops_job_oldest_active_seconds{job_type="PROFILE_SCAN"}' in response.text
    job_lines = [line for line in response.text.splitlines() if line.startswith("social_ops_job")]
    assert all(workspace["id"] not in line for line in job_lines)
    assert (
        f'social_ops_provider_budget_utilization_ratio{{workspace_id="{workspace["id"]}"}}'
        in response.text
    )


def test_metrics_token_is_required_when_configured():
    settings = Settings(
        _env_file=None,
        app_env="test",
        auth_mode="development",
        database_url="sqlite:///:memory:",
        metrics_bearer_token="metrics-secret",
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.database.engine)

    with TestClient(application) as client:
        assert client.get("/metrics").status_code == 401
        response = client.get(
            "/metrics",
            headers={"Authorization": "Bearer metrics-secret"},
        )

    assert response.status_code == 200


def test_metrics_can_be_disabled():
    settings = Settings(
        _env_file=None,
        app_env="test",
        auth_mode="development",
        database_url="sqlite:///:memory:",
        metrics_enabled=False,
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.database.engine)

    with TestClient(application) as client:
        response = client.get("/metrics")

    assert response.status_code == 404
