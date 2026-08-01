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
    WorkspaceInspiration,
)


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _inspiration(
    db,
    *,
    workspace_id: UUID,
    external_id: str,
    title: str | None = None,
    body_text: str | None = None,
    notes: str | None = None,
    platform: str = "xiaohongshu",
    source: str = "test",
    created_at: datetime | None = None,
) -> WorkspaceInspiration:
    content = ExternalContent(
        workspace_id=workspace_id,
        platform=platform,
        external_id=external_id,
        canonical_url=f"https://example.test/{external_id}",
        content_type="image_text",
        title=title,
        body_text=body_text,
        author_snapshot={},
        media_manifest=[],
    )
    db.add(content)
    db.flush()
    inspiration = WorkspaceInspiration(
        workspace_id=workspace_id,
        external_content_id=content.id,
        source=source,
        notes=notes,
    )
    if created_at is not None:
        inspiration.created_at = created_at
    db.add(inspiration)
    return inspiration


def test_inspiration_list_searches_title_body_notes_and_platform(
    client, app, auth_headers, workspace
):
    with app.state.database.session_factory() as db:
        workspace_id = UUID(workspace["id"])
        _inspiration(db, workspace_id=workspace_id, external_id="title", title="门店增长")
        _inspiration(db, workspace_id=workspace_id, external_id="body", body_text="套餐复购")
        _inspiration(db, workspace_id=workspace_id, external_id="notes", notes="研究笔记洞察")
        _inspiration(
            db,
            workspace_id=workspace_id,
            external_id="platform",
            platform="youtube",
        )
        db.commit()

    headers = _headers(auth_headers, workspace)
    expected = {
        "门店增长": "title",
        "套餐复购": "body",
        "研究笔记洞察": "notes",
        "youtube": "platform",
    }
    for query, external_id in expected.items():
        response = client.get("/api/v1/inspirations", params={"query": query}, headers=headers)
        assert response.status_code == 200
        assert [item["content"]["external_id"] for item in response.json()["data"]] == [
            external_id
        ]


def test_inspiration_list_uses_descending_keyset_cursor(client, app, auth_headers, workspace):
    now = datetime.now(timezone.utc)
    with app.state.database.session_factory() as db:
        workspace_id = UUID(workspace["id"])
        for index in range(3):
            _inspiration(
                db,
                workspace_id=workspace_id,
                external_id=f"page-{index}",
                created_at=now + timedelta(seconds=index),
            )
        db.commit()

    headers = _headers(auth_headers, workspace)
    first = client.get("/api/v1/inspirations", params={"limit": 2}, headers=headers)
    assert first.status_code == 200
    first_data = first.json()
    assert [item["content"]["external_id"] for item in first_data["data"]] == [
        "page-2",
        "page-1",
    ]
    assert first_data["meta"]["next_cursor"]

    second = client.get(
        "/api/v1/inspirations",
        params={"limit": 2, "cursor": first_data["meta"]["next_cursor"]},
        headers=headers,
    )
    assert [item["content"]["external_id"] for item in second.json()["data"]] == ["page-0"]
    assert second.json()["meta"]["next_cursor"] is None


def test_inspiration_list_hides_legacy_unqualified_tracked_profile_items(
    client, app, auth_headers, workspace
):
    workspace_id = UUID(workspace["id"])
    score_time = datetime.now(timezone.utc)
    with app.state.database.session_factory() as db:
        tracked = _inspiration(
            db,
            workspace_id=workspace_id,
            external_id="legacy-tracked",
            title="legacy tracked signal",
            source="tracked_profile",
        )
        _inspiration(
            db,
            workspace_id=workspace_id,
            external_id="manual-import",
            source="manual_url",
        )
        policy = db.scalar(
            select(ScoringPolicy).where(
                ScoringPolicy.workspace_id == workspace_id,
                ScoringPolicy.platform == "xiaohongshu",
                ScoringPolicy.active.is_(True),
            )
        )
        assert policy is not None
        tracked_inspiration_id = tracked.id
        tracked_content_id = tracked.external_content_id
        policy_id = policy.id
        db.add(
            ContentScore(
                workspace_id=workspace_id,
                external_content_id=tracked_content_id,
                scoring_policy_id=policy_id,
                grade="insufficient",
                calculated_at=score_time - timedelta(minutes=1),
                is_initial=True,
                evidence={},
            )
        )
        db.commit()

    headers = _headers(auth_headers, workspace)
    initial = client.get("/api/v1/inspirations", headers=headers)
    assert [item["content"]["external_id"] for item in initial.json()["data"]] == [
        "manual-import"
    ]
    initial_search = client.get(
        "/api/v1/search",
        params={"q": "legacy tracked signal", "type": "inspiration"},
        headers=headers,
    )
    assert initial_search.json()["data"] == []

    with app.state.database.session_factory() as db:
        db.add(
            ContentScore(
                workspace_id=workspace_id,
                external_content_id=tracked_content_id,
                scoring_policy_id=policy_id,
                grade="t1",
                calculated_at=score_time,
                is_initial=False,
                evidence={},
            )
        )
        db.commit()

    promoted = client.get("/api/v1/inspirations", headers=headers)
    assert {item["content"]["external_id"] for item in promoted.json()["data"]} == {
        "legacy-tracked",
        "manual-import",
    }
    promoted_search = client.get(
        "/api/v1/search",
        params={"q": "legacy tracked signal", "type": "inspiration"},
        headers=headers,
    )
    assert [item["entity_id"] for item in promoted_search.json()["data"]] == [
        str(tracked_inspiration_id)
    ]


def test_inspiration_list_includes_latest_score_and_metric_summary(
    client, app, auth_headers, workspace
):
    workspace_id = UUID(workspace["id"])
    captured_at = datetime.now(timezone.utc)
    with app.state.database.session_factory() as db:
        inspiration = _inspiration(
            db,
            workspace_id=workspace_id,
            external_id="card-summary",
            source="manual_url",
        )
        policy = db.scalar(
            select(ScoringPolicy).where(
                ScoringPolicy.workspace_id == workspace_id,
                ScoringPolicy.platform == "xiaohongshu",
                ScoringPolicy.active.is_(True),
            )
        )
        assert policy is not None
        fetch = ProviderFetch(
            workspace_id=workspace_id,
            provider="fixture",
            platform="xiaohongshu",
            endpoint_key="fixture.content",
            endpoint_path="/fixture",
            request_fingerprint="card-summary-fetch",
            request_params_redacted={},
            billable=False,
            estimated_cost_usd=Decimal("0"),
        )
        db.add(fetch)
        db.flush()
        db.add_all(
            [
                ContentScore(
                    workspace_id=workspace_id,
                    external_content_id=inspiration.external_content_id,
                    scoring_policy_id=policy.id,
                    grade="ordinary",
                    r_value=Decimal("1.2"),
                    is_initial=True,
                    evidence={},
                    calculated_at=captured_at - timedelta(minutes=1),
                ),
                ContentScore(
                    workspace_id=workspace_id,
                    external_content_id=inspiration.external_content_id,
                    scoring_policy_id=policy.id,
                    grade="t2",
                    r_value=Decimal("3.5"),
                    is_initial=False,
                    evidence={},
                    calculated_at=captured_at,
                ),
                ContentMetricSnapshot(
                    workspace_id=workspace_id,
                    external_content_id=inspiration.external_content_id,
                    provider_fetch_id=fetch.id,
                    captured_at=captured_at,
                    views=12_000,
                    likes=600,
                    comments=30,
                    favorites=70,
                    shares=8,
                    metrics={},
                ),
            ]
        )
        db.commit()

    response = client.get("/api/v1/inspirations", headers=_headers(auth_headers, workspace))
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert item["latest_score"]["grade"] == "t2"
    assert item["latest_score"]["r_value"] == "3.500000"
    assert item["latest_metrics"]["captured_at"].startswith(
        captured_at.isoformat().replace("+00:00", "")
    )
    assert item["latest_metrics"] | {"captured_at": None} == {
        "captured_at": None,
        "views": 12_000,
        "likes": 600,
        "comments": 30,
        "favorites": 70,
        "shares": 8,
    }
