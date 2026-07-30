import uuid

from sqlalchemy import select

from app.db.models import User, WorkspaceMember


def _workspace_headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _create_profile(client, headers, external_id="profile-1"):
    return client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": external_id,
            "profile_url": f"https://www.xiaohongshu.com/user/profile/{external_id}",
            "display_name": "Competitor",
        },
    )


def test_profile_sync_is_deduplicated_while_active(client, auth_headers, workspace):
    headers = _workspace_headers(auth_headers, workspace)
    created = _create_profile(client, headers)
    assert created.status_code == 201
    profile_id = created.json()["data"]["id"]

    first = client.post(f"/api/v1/tracked-profiles/{profile_id}/sync", headers=headers)
    second = client.post(f"/api/v1/tracked-profiles/{profile_id}/sync", headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]


def test_profile_sync_natural_dedupe_ignores_different_request_keys(
    client,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    profile_id = _create_profile(client, headers).json()["data"]["id"]

    first = client.post(
        f"/api/v1/tracked-profiles/{profile_id}/sync",
        headers={**headers, "Idempotency-Key": "request-one"},
    )
    second = client.post(
        f"/api/v1/tracked-profiles/{profile_id}/sync",
        headers={**headers, "Idempotency-Key": "request-two"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]


def test_workspace_isolation_hides_profiles(client, auth_headers, workspace):
    headers = _workspace_headers(auth_headers, workspace)
    created = _create_profile(client, headers)
    profile_id = created.json()["data"]["id"]

    other = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Other", "timezone": "UTC"},
    ).json()["data"]
    isolated_headers = {**auth_headers, "X-Workspace-Id": other["id"]}

    response = client.get(
        f"/api/v1/tracked-profiles/{profile_id}",
        headers=isolated_headers,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_duplicate_platform_profile_is_rejected(client, auth_headers, workspace):
    headers = _workspace_headers(auth_headers, workspace)
    assert _create_profile(client, headers).status_code == 201

    duplicate = _create_profile(client, headers)

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"


def test_batch_import_and_soft_delete_profile(client, auth_headers, workspace):
    headers = _workspace_headers(auth_headers, workspace)
    response = client.post(
        "/api/v1/tracked-profiles/import",
        headers=headers,
        json={
            "profiles": [
                {
                    "platform": "xiaohongshu",
                    "external_id": "batch-xhs",
                    "profile_url": "https://www.xiaohongshu.com/user/profile/batch-xhs",
                    "display_name": "Batch XHS",
                },
                {
                    "platform": "douyin",
                    "external_id": "batch-douyin",
                    "profile_url": "https://www.douyin.com/user/batch-douyin",
                    "display_name": "Batch Douyin",
                },
            ]
        },
    )
    assert response.status_code == 201
    assert [item["external_id"] for item in response.json()["data"]] == [
        "batch-xhs",
        "batch-douyin",
    ]

    profile_id = response.json()["data"][0]["id"]
    deleted = client.delete(f"/api/v1/tracked-profiles/{profile_id}", headers=headers)
    assert deleted.status_code == 204

    detail = client.get(f"/api/v1/tracked-profiles/{profile_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["active"] is False
    assert detail.json()["data"]["sync_status"] == "paused"


def test_batch_import_is_atomic_when_request_contains_duplicates(
    client,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    item = {
        "platform": "xiaohongshu",
        "external_id": "same-profile",
        "profile_url": "https://www.xiaohongshu.com/user/profile/same-profile",
        "display_name": "Same",
    }
    response = client.post(
        "/api/v1/tracked-profiles/import",
        headers=headers,
        json={"profiles": [item, item]},
    )
    assert response.status_code == 409
    assert client.get("/api/v1/tracked-profiles", headers=headers).json()["data"] == []


def test_viewer_cannot_create_paid_sync_job(client, app, auth_headers, workspace):
    owner_headers = _workspace_headers(auth_headers, workspace)
    profile_id = _create_profile(client, owner_headers).json()["data"]["id"]

    viewer_auth = {"Authorization": "Bearer dev:test-viewer"}
    assert client.get("/api/v1/me", headers=viewer_auth).status_code == 200
    with app.state.database.session_factory() as db:
        viewer = db.scalar(select(User).where(User.external_subject == "test-viewer"))
        db.add(
            WorkspaceMember(
                workspace_id=uuid.UUID(workspace["id"]),
                user_id=viewer.id,
                role="viewer",
            )
        )
        db.commit()

    response = client.post(
        f"/api/v1/tracked-profiles/{profile_id}/sync",
        headers={**viewer_auth, "X-Workspace-Id": workspace["id"]},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
