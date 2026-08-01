import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.models import (
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    ProviderFetch,
    ScoringPolicy,
    SyncJob,
    User,
    WorkspaceInspiration,
    WorkspaceMember,
)


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
    detail = client.get(f"/api/v1/tracked-profiles/{profile_id}", headers=headers)
    assert detail.json()["data"]["sync_status"] == "pending"


def test_profile_sync_reflects_reused_running_job(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    profile_id = _create_profile(client, headers, external_id="running-sync").json()["data"][
        "id"
    ]
    first = client.post(f"/api/v1/tracked-profiles/{profile_id}/sync", headers=headers)
    job_id = UUID(first.json()["data"]["job_id"])
    with app.state.database.session_factory() as db:
        job = db.get(SyncJob, job_id)
        assert job is not None
        job.status = "running"
        db.commit()

    reused = client.post(f"/api/v1/tracked-profiles/{profile_id}/sync", headers=headers)

    assert reused.status_code == 202
    assert reused.json()["data"] == {"job_id": str(job_id), "status": "running"}
    detail = client.get(f"/api/v1/tracked-profiles/{profile_id}", headers=headers)
    assert detail.json()["data"]["sync_status"] == "syncing"


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


def test_profile_overview_returns_recent_content_intelligence(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    profile_id = UUID(_create_profile(client, headers).json()["data"]["id"])
    workspace_id = UUID(workspace["id"])
    now = datetime.now(timezone.utc)

    with app.state.database.session_factory() as db:
        policy = db.scalar(
            select(ScoringPolicy).where(
                ScoringPolicy.workspace_id == workspace_id,
                ScoringPolicy.platform == "xiaohongshu",
                ScoringPolicy.active.is_(True),
            )
        )
        assert policy is not None

        contents = []
        for index, (external_id, published_days_ago, first_seen_days_ago) in enumerate(
            [
                ("newest-t2", 1, 1),
                ("second-t1", 2, 2),
                ("recent-normal", 3, 3),
                ("recent-qualified", 4, 4),
                ("old-t3", 40, 40),
                ("deleted-at-source", 1, 1),
            ]
        ):
            content = ExternalContent(
                workspace_id=workspace_id,
                platform="xiaohongshu",
                external_id=external_id,
                tracked_profile_id=profile_id,
                canonical_url=f"https://example.test/{external_id}",
                content_type="image_text",
                title=f"Content {external_id}",
                published_at=now - timedelta(days=published_days_ago),
                first_seen_at=now - timedelta(days=first_seen_days_ago),
                author_snapshot={},
                media_manifest=(
                    [{"type": "cover", "url": "https://media.test/newest.jpg"}]
                    if index == 0
                    else []
                ),
            )
            db.add(content)
            db.flush()
            contents.append(content)

        newest, second, _, qualified, old, deleted = contents
        deleted.deleted_at_source = now
        for suffix, captured_at, likes in [
            ("older", now - timedelta(hours=2), 10),
            ("latest", now - timedelta(hours=1), 99),
        ]:
            provider_fetch = ProviderFetch(
                workspace_id=workspace_id,
                provider="test",
                platform="xiaohongshu",
                endpoint_key="overview-fixture",
                endpoint_path="/fixture",
                request_fingerprint=f"overview-{suffix}",
                request_params_redacted={},
                billable=False,
                estimated_cost_usd=Decimal("0"),
                response_payload={},
            )
            db.add(provider_fetch)
            db.flush()
            db.add(
                ContentMetricSnapshot(
                    workspace_id=workspace_id,
                    external_content_id=newest.id,
                    captured_at=captured_at,
                    views=likes * 10,
                    likes=likes,
                    comments=likes // 10,
                    metrics={},
                    provider_fetch_id=provider_fetch.id,
                )
            )

        for content, grade, calculated_at in [
            (newest, "t1", now - timedelta(hours=2)),
            (newest, "t2", now - timedelta(hours=1)),
            (second, "t1", now - timedelta(hours=1)),
            (qualified, "qualified", now - timedelta(hours=1)),
            (old, "t3", now - timedelta(hours=1)),
        ]:
            db.add(
                ContentScore(
                    workspace_id=workspace_id,
                    external_content_id=content.id,
                    scoring_policy_id=policy.id,
                    calculated_at=calculated_at,
                    grade=grade,
                    tier="micro",
                    is_initial=False,
                    evidence={},
                )
            )
        inspiration = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=newest.id,
            source="tracked_profile",
        )
        db.add(inspiration)
        db.commit()

    response = client.get(
        f"/api/v1/tracked-profiles/{profile_id}/overview",
        params={"window_days": 30, "limit": 2},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profile"]["id"] == str(profile_id)
    assert data["window_days"] == 30
    assert data["total_content_count"] == 5
    assert data["recent_content_count"] == 4
    assert data["grade_distribution"] == {
        "t1": 1,
        "t2": 1,
        "t3": 0,
        "qualified": 1,
        "normal": 1,
    }
    assert [item["external_id"] for item in data["contents"]] == [
        "newest-t2",
        "second-t1",
    ]
    latest = data["contents"][0]
    assert latest["cover_url"] == "https://media.test/newest.jpg"
    assert latest["latest_metrics"]["likes"] == 99
    assert latest["latest_score"]["grade"] == "t2"
    assert latest["in_inspiration_library"] is True
    assert latest["inspiration_id"] == str(inspiration.id)


def test_profile_overview_has_zero_defaults_and_is_workspace_isolated(
    client,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    profile_id = _create_profile(client, headers, external_id="overview-empty").json()["data"][
        "id"
    ]

    empty = client.get(f"/api/v1/tracked-profiles/{profile_id}/overview", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["data"]["total_content_count"] == 0
    assert empty.json()["data"]["recent_content_count"] == 0
    assert empty.json()["data"]["grade_distribution"] == {
        "t1": 0,
        "t2": 0,
        "t3": 0,
        "qualified": 0,
        "normal": 0,
    }
    assert empty.json()["data"]["contents"] == []

    other = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Overview isolation", "timezone": "UTC"},
    ).json()["data"]
    isolated = client.get(
        f"/api/v1/tracked-profiles/{profile_id}/overview",
        headers={**auth_headers, "X-Workspace-Id": other["id"]},
    )
    assert isolated.status_code == 404
    assert isolated.json()["code"] == "NOT_FOUND"


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
