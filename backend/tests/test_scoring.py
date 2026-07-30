from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.models import (
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    ProfileMetricSnapshot,
    ProviderFetch,
    ScoringPolicy,
    WorkspaceInspiration,
)


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _provider_fetch(workspace_id, fingerprint):
    return ProviderFetch(
        workspace_id=workspace_id,
        provider="tikhub",
        platform="xiaohongshu",
        endpoint_key="fixture",
        endpoint_path="/fixture",
        request_fingerprint=fingerprint,
        request_params_redacted={},
        billable=False,
        estimated_cost_usd=Decimal("0"),
        response_payload={},
    )


def _seed_scoring_series(client, app, auth_headers, workspace, *, prior_count=5):
    headers = _headers(auth_headers, workspace)
    profile_data = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": f"score-profile-{prior_count}",
            "profile_url": f"https://www.xiaohongshu.com/user/profile/score-{prior_count}",
            "display_name": "Score fixture",
        },
    ).json()["data"]
    workspace_id = UUID(workspace["id"])
    profile_id = UUID(profile_data["id"])
    now = datetime.now(timezone.utc)
    with app.state.database.session_factory() as db:
        follower_fetch = _provider_fetch(workspace_id, f"followers-{prior_count}")
        db.add(follower_fetch)
        db.flush()
        db.add(
            ProfileMetricSnapshot(
                workspace_id=workspace_id,
                tracked_profile_id=profile_id,
                followers=1000,
                metrics={},
                provider_fetch_id=follower_fetch.id,
            )
        )
        prior_ids = []
        for index in range(prior_count):
            fetch = _provider_fetch(workspace_id, f"prior-{prior_count}-{index}")
            content = ExternalContent(
                workspace_id=workspace_id,
                platform="xiaohongshu",
                external_id=f"prior-{prior_count}-{index}",
                tracked_profile_id=profile_id,
                canonical_url=f"https://www.xiaohongshu.com/explore/prior-{index}",
                content_type="image_text",
                published_at=now - timedelta(days=prior_count - index + 2),
                author_snapshot={},
                media_manifest=[],
            )
            db.add_all([fetch, content])
            db.flush()
            prior_ids.append(str(content.id))
            db.add(
                ContentMetricSnapshot(
                    workspace_id=workspace_id,
                    external_content_id=content.id,
                    likes=(index + 1) * 10,
                    comments=0,
                    favorites=0,
                    shares=0,
                    metrics={},
                    provider_fetch_id=fetch.id,
                )
            )

        candidate_fetch = _provider_fetch(workspace_id, f"candidate-{prior_count}")
        candidate = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id=f"candidate-{prior_count}",
            tracked_profile_id=profile_id,
            canonical_url=f"https://www.xiaohongshu.com/explore/candidate-{prior_count}",
            content_type="image_text",
            published_at=now - timedelta(days=1),
            author_snapshot={},
            media_manifest=[],
        )
        db.add_all([candidate_fetch, candidate])
        db.flush()
        db.add(
            ContentMetricSnapshot(
                workspace_id=workspace_id,
                external_content_id=candidate.id,
                likes=300,
                comments=0,
                favorites=0,
                shares=0,
                metrics={},
                provider_fetch_id=candidate_fetch.id,
            )
        )
        inspiration = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=candidate.id,
            source="test",
        )
        db.add(inspiration)
        db.commit()
        return str(inspiration.id), prior_ids


def test_score_uses_only_prior_baseline_and_freezes_initial_evidence(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, prior_ids = _seed_scoring_series(
        client,
        app,
        auth_headers,
        workspace,
    )
    headers = _headers(auth_headers, workspace)

    first = client.post(
        f"/api/v1/inspirations/{inspiration_id}/scores/recalculate",
        headers=headers,
    )
    second = client.post(
        f"/api/v1/inspirations/{inspiration_id}/scores/recalculate",
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    initial = first.json()["data"]
    later = second.json()["data"]
    assert initial["is_initial"] is True
    assert later["is_initial"] is False
    assert Decimal(initial["baseline_value"]) == Decimal("30")
    assert Decimal(initial["r_value"]) == Decimal("10")
    assert initial["grade"] == "t1"
    assert set(initial["evidence"]["baseline_content_ids"]) == set(prior_ids)

    listing = client.get(
        f"/api/v1/inspirations/{inspiration_id}/scores",
        headers=headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2

    metrics = client.get(
        f"/api/v1/inspirations/{inspiration_id}/metrics",
        headers=headers,
    )
    assert metrics.status_code == 200
    assert len(metrics.json()["data"]) == 1
    assert metrics.json()["data"][0]["likes"] == 300
    assert metrics.json()["data"][0]["views"] is None
    with app.state.database.session_factory() as db:
        initial_rows = db.scalars(select(ContentScore).where(ContentScore.is_initial)).all()
        assert len(initial_rows) == 1


def test_score_marks_insufficient_baseline_without_forcing_grade(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_scoring_series(
        client,
        app,
        auth_headers,
        workspace,
        prior_count=1,
    )

    response = client.post(
        f"/api/v1/inspirations/{inspiration_id}/scores/recalculate",
        headers=_headers(auth_headers, workspace),
    )

    assert response.status_code == 201
    score = response.json()["data"]
    assert score["grade"] == "insufficient"
    assert score["r_value"] is None
    assert "insufficient_baseline" in score["evidence"]["reasons"]


def test_new_policy_version_can_be_activated_without_rewriting_history(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    body = {
        "platform": "xiaohongshu",
        "core_metric_formula": {
            "required_metrics": ["likes"],
            "core_metric_weights": {"likes": 1},
            "reach_proxy_weights": {"likes": 1},
        },
        "tier_thresholds": {
            "micro_max": 1000,
            "small_max": 10000,
            "medium_max": 100000,
        },
        "grade_thresholds": {
            "t1": {"minimum_r": 4, "minimum_m": 0.1},
            "t2": {"minimum_r": 2, "minimum_m": 0.05},
            "t3": {"minimum_r": 1.5, "minimum_m": 0},
            "low_quality": {"maximum_r": 0.5},
        },
        "minimum_baseline_count": 3,
    }
    created = client.post("/api/v1/scoring-policies", headers=headers, json=body)
    assert created.status_code == 201
    assert created.json()["data"]["version"] == 2
    assert created.json()["data"]["active"] is False

    activated = client.post(
        f"/api/v1/scoring-policies/{created.json()['data']['id']}/activate",
        headers=headers,
    )
    assert activated.status_code == 200
    assert activated.json()["data"]["active"] is True

    with app.state.database.session_factory() as db:
        policies = db.scalars(
            select(ScoringPolicy)
            .where(ScoringPolicy.workspace_id == UUID(workspace["id"]))
            .order_by(ScoringPolicy.version)
        ).all()
        assert [policy.active for policy in policies] == [False, True]
