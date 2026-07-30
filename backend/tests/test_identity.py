import uuid

from sqlalchemy import select

from app.db.models import ScanPolicy


def test_me_requires_authentication(client):
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_workspace_creation_adds_owner_membership(client, auth_headers, workspace):
    response = client.get("/api/v1/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["memberships"] == [
        {"workspace_id": workspace["id"], "role": "owner"}
    ]


def test_workspace_creation_uses_daily_scan_policy(client, app, workspace):
    with app.state.database.session_factory() as db:
        policy = db.scalar(
            select(ScanPolicy).where(ScanPolicy.workspace_id == uuid.UUID(workspace["id"]))
        )
        assert policy is not None
        assert policy.schedule == {"interval_hours": 24}


def test_workspace_detail_and_owner_update_are_scoped(client, auth_headers, workspace):
    detail = client.get(f"/api/v1/workspaces/{workspace['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == workspace["id"]

    updated = client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        headers=auth_headers,
        json={
            "name": "Updated workspace",
            "timezone": "UTC",
            "daily_provider_budget_usd": "12.50",
            "daily_ai_budget_usd": "8.25",
            "settings": {"feature_flags": {"semantic_search": False}},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Updated workspace"
    assert updated.json()["data"]["timezone"] == "UTC"
    assert updated.json()["data"]["daily_provider_budget_usd"] == "12.50"

    outsider = client.get(
        f"/api/v1/workspaces/{workspace['id']}",
        headers={"Authorization": "Bearer dev:workspace-outsider"},
    )
    assert outsider.status_code == 404


def test_owner_can_pause_and_resume_external_calls(client, auth_headers, workspace):
    paused = client.post(
        f"/api/v1/workspaces/{workspace['id']}/external-calls/pause",
        headers=auth_headers,
        json={"reason": "Provider incident drill"},
    )
    assert paused.status_code == 200
    assert paused.json()["data"]["paused"] is True
    assert paused.json()["data"]["reason"] == "Provider incident drill"

    detail = client.get(f"/api/v1/workspaces/{workspace['id']}", headers=auth_headers)
    assert detail.json()["data"]["settings"]["external_calls"]["paused"] is True

    resumed = client.post(
        f"/api/v1/workspaces/{workspace['id']}/external-calls/resume",
        headers=auth_headers,
    )
    assert resumed.status_code == 200
    assert resumed.json()["data"]["paused"] is False
