import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models import (
    AnalysisRun,
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    ProviderFetch,
    SyncJob,
    User,
    Workspace,
    WorkspaceInspiration,
    WorkspaceMember,
)
from app.jobs.service import schedule_due_profile_scans
from app.jobs.worker import process_one
from app.modules.automation.schemas import AutomationSettings, MetricThresholds
from app.modules.automation.service import evaluate_hard_gate, within_daily_analysis_limit
from app.providers.ai.fixture import FixtureAnalysisProvider
from app.providers.social.tikhub.client import TikHubHttpClient

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _provider_fetch(workspace_id, fingerprint: str) -> ProviderFetch:
    return ProviderFetch(
        workspace_id=workspace_id,
        provider="tikhub",
        platform="xiaohongshu",
        endpoint_key="automation-fixture",
        endpoint_path="/automation-fixture",
        request_fingerprint=fingerprint,
        request_params_redacted={},
        billable=False,
        estimated_cost_usd=Decimal("0"),
        response_payload={},
    )


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_automation_settings_are_workspace_scoped_partial_and_owner_managed(
    client,
    app,
    auth_headers,
    workspace,
):
    owner_headers = _headers(auth_headers, workspace)
    initial = client.get("/api/v1/automation/settings", headers=owner_headers)
    assert initial.status_code == 200
    assert initial.json()["data"]["enabled"] is True
    initial_comments_threshold = initial.json()["data"]["metric_thresholds"]["comments"]

    updated = client.patch(
        "/api/v1/automation/settings",
        headers=owner_headers,
        json={
            "threshold_match": "all",
            "daily_l1_limit": 3,
            "metric_thresholds": {"likes": 250},
        },
    )
    assert updated.status_code == 200
    settings = updated.json()["data"]
    assert settings["threshold_match"] == "all"
    assert settings["daily_l1_limit"] == 3
    assert settings["metric_thresholds"]["likes"] == 250
    assert settings["metric_thresholds"]["comments"] == initial_comments_threshold

    viewer_auth = {"Authorization": "Bearer dev:automation-viewer"}
    assert client.get("/api/v1/me", headers=viewer_auth).status_code == 200
    with app.state.database.session_factory() as db:
        viewer = db.scalar(select(User).where(User.external_subject == "automation-viewer"))
        db.add(
            WorkspaceMember(
                workspace_id=UUID(workspace["id"]),
                user_id=viewer.id,
                role="viewer",
            )
        )
        db.commit()
    viewer_headers = {**viewer_auth, "X-Workspace-Id": workspace["id"]}
    readable = client.get("/api/v1/automation/settings", headers=viewer_headers)
    forbidden = client.patch(
        "/api/v1/automation/settings",
        headers=viewer_headers,
        json={"enabled": False},
    )
    assert readable.status_code == 200
    assert forbidden.status_code == 403

    invalid = client.patch(
        "/api/v1/automation/settings",
        headers=owner_headers,
        json={"metric_thresholds": {"likes": -1}},
    )
    assert invalid.status_code == 422


def test_hard_gate_rechecks_latest_metrics_without_author_or_ai_side_effects(app, workspace):
    workspace_id = UUID(workspace["id"])
    now = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    with app.state.database.session_factory() as db:
        current_workspace = db.get(Workspace, workspace_id)
        first_fetch = _provider_fetch(workspace_id, "automation-below")
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="automation-authorless",
            canonical_url="https://www.xiaohongshu.com/explore/automation-authorless",
            content_type="image_text",
            title="Authorless candidate",
            published_at=now - timedelta(hours=2),
            author_snapshot={},
            media_manifest=[],
        )
        db.add_all([first_fetch, content])
        db.flush()
        db.add(
            ContentMetricSnapshot(
                workspace_id=workspace_id,
                external_content_id=content.id,
                captured_at=now - timedelta(minutes=2),
                views=999,
                likes=99,
                comments=0,
                favorites=0,
                shares=0,
                metrics={},
                provider_fetch_id=first_fetch.id,
            )
        )
        db.flush()
        policy = AutomationSettings(
            minimum_age_minutes=60,
            observation_hours=72,
            metric_thresholds=MetricThresholds(likes=100),
            threshold_match="any",
        )

        below = evaluate_hard_gate(
            db,
            workspace=current_workspace,
            content=content,
            policy=policy,
            now=now,
        )
        assert below.passed is False
        assert below.observing is True
        assert below.evidence["reasons"] == ["metric_threshold_not_reached"]
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 0

        second_fetch = _provider_fetch(workspace_id, "automation-above")
        db.add(second_fetch)
        db.flush()
        db.add(
            ContentMetricSnapshot(
                workspace_id=workspace_id,
                external_content_id=content.id,
                captured_at=now - timedelta(minutes=1),
                views=1_000,
                likes=100,
                comments=0,
                favorites=0,
                shares=0,
                metrics={},
                provider_fetch_id=second_fetch.id,
            )
        )
        db.flush()

        above = evaluate_hard_gate(
            db,
            workspace=current_workspace,
            content=content,
            policy=policy,
            now=now,
        )
        assert above.passed is True
        assert above.observing is False
        assert above.evidence["actual"]["likes"] == 100
        assert content.tracked_profile_id is None
        assert content.author_snapshot == {}


def test_daily_analysis_limit_counts_only_active_or_succeeded_runs(app, workspace):
    workspace_id = UUID(workspace["id"])
    now = datetime.now(timezone.utc)
    with app.state.database.session_factory() as db:
        current_workspace = db.get(Workspace, workspace_id)
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="x",
            external_id="automation-daily-limit",
            canonical_url="https://x.com/example/status/automation-daily-limit",
            content_type="tweet",
            title="Daily limit fixture",
            published_at=now - timedelta(hours=2),
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        for index, status in enumerate(("succeeded", "failed")):
            db.add(
                AnalysisRun(
                    workspace_id=workspace_id,
                    external_content_id=content.id,
                    analysis_level="l1",
                    model_provider="fixture",
                    model="fixture-l1",
                    prompt_version="fixture-v1",
                    input_hash=f"automation-limit-{index}",
                    status=status,
                    evidence_refs=[f"content:{content.id}"],
                    created_at=now,
                )
            )
        db.flush()
        policy = AutomationSettings(daily_l1_limit=2)
        assert within_daily_analysis_limit(
            db,
            workspace=current_workspace,
            level="l1",
            policy=policy,
        ) is True

        db.add(
            AnalysisRun(
                workspace_id=workspace_id,
                external_content_id=content.id,
                analysis_level="l1",
                model_provider="fixture",
                model="fixture-l1",
                prompt_version="fixture-v1",
                input_hash="automation-limit-active-2",
                status="queued",
                evidence_refs=[f"content:{content.id}"],
                created_at=now,
            )
        )
        db.flush()
        assert within_daily_analysis_limit(
            db,
            workspace=current_workspace,
            level="l1",
            policy=policy,
        ) is False
        assert within_daily_analysis_limit(
            db,
            workspace=current_workspace,
            level="l2",
            policy=AutomationSettings(daily_l2_limit=0),
        ) is False


def test_scheduler_does_not_enqueue_scans_when_workspace_automation_is_disabled(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    profile = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": "automation-disabled-profile",
            "profile_url": (
                "https://www.xiaohongshu.com/user/profile/automation-disabled-profile"
            ),
            "display_name": "Disabled automation fixture",
        },
    )
    assert profile.status_code == 201
    disabled = client.patch(
        "/api/v1/automation/settings",
        headers=headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200

    with app.state.database.session_factory() as db:
        created, deduplicated = schedule_due_profile_scans(db)
        db.commit()
        assert (created, deduplicated) == (0, 0)
        assert db.scalar(select(func.count()).select_from(SyncJob)) == 0


@pytest.mark.parametrize(
    ("automation_enabled", "daily_l2_limit", "expected_l2_count", "expected_status"),
    [
        (True, 1, 1, "queued"),
        (True, 0, 0, "daily_limit_reached"),
        (False, 1, 0, "disabled"),
    ],
)
def test_recommending_l1_automatically_queues_l2_once_within_daily_limit(
    client,
    app,
    auth_headers,
    workspace,
    automation_enabled,
    daily_l2_limit,
    expected_l2_count,
    expected_status,
):
    workspace_id = UUID(workspace["id"])
    headers = _headers(auth_headers, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-analysis"
    configured = client.patch(
        "/api/v1/automation/settings",
        headers=headers,
        json={
            "enabled": automation_enabled,
            "auto_l2": True,
            "daily_l2_limit": daily_l2_limit,
        },
    )
    assert configured.status_code == 200

    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id=f"automation-auto-l2-{daily_l2_limit}",
            canonical_url=(
                "https://www.xiaohongshu.com/explore/"
                f"automation-auto-l2-{daily_l2_limit}"
            ),
            content_type="image_text",
            title="Manual high-potential candidate",
            body_text="A manually selected content fixture.",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        inspiration = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=content.id,
            source="manual_url",
        )
        db.add(inspiration)
        db.commit()
        inspiration_id = inspiration.id

    requested = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l1"},
    )
    assert requested.status_code == 202

    async def run_l1():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(500, json={"unused": True})
            )
        ) as http_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="unused",
                client=http_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id=f"automation-l1-{daily_l2_limit}",
                    analysis_provider=FixtureAnalysisProvider(),
                    settings=app.state.settings,
                )

    assert asyncio.run(run_l1()) is True
    with app.state.database.session_factory() as db:
        runs = db.scalars(
            select(AnalysisRun).order_by(AnalysisRun.analysis_level)
        ).all()
        l1 = [run for run in runs if run.analysis_level == "l1"]
        l2 = [run for run in runs if run.analysis_level == "l2"]
        assert len(l1) == 1
        assert l1[0].status == "succeeded"
        assert len(l2) == expected_l2_count
        if l2:
            assert l2[0].status == "queued"
        l1_job = db.get(SyncJob, l1[0].sync_job_id)
        assert l1_job.result["auto_l2_status"] == expected_status


def test_profile_scan_calls_no_ai_before_gate_then_rechecks_and_queues_l1(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-analysis"
    configured = client.patch(
        "/api/v1/automation/settings",
        headers=headers,
        json={
            "enabled": True,
            "minimum_age_minutes": 0,
            "metric_thresholds": {
                "views": 0,
                "likes": 50_000,
                "comments": 0,
                "favorites": 0,
                "shares": 0,
            },
            "threshold_match": "any",
            "auto_l1": True,
            "daily_l1_limit": 5,
        },
    )
    assert configured.status_code == 200
    profile = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": "automation-recheck-profile",
            "profile_url": (
                "https://www.xiaohongshu.com/user/profile/automation-recheck-profile"
            ),
            "display_name": "Automation recheck fixture",
        },
    ).json()["data"]
    first_job_id = client.post(
        f"/api/v1/tracked-profiles/{profile['id']}/sync",
        headers=headers,
    ).json()["data"]["job_id"]

    should_pass = False

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/get_user_info"):
            payload = _fixture("xhs_profile_representative.json")
            return httpx.Response(200, json=payload)
        payload = _fixture("xhs_profile_notes_representative.json")
        if request.url.params.get("cursor"):
            payload["data"]["data"]["notes"] = []
        elif should_pass:
            payload["data"]["data"]["notes"][0]["likes"] = 60_000
        return httpx.Response(200, json=payload)

    async def run_scan(worker_id: str):
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="test",
                client=raw_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id=worker_id,
                    settings=app.state.settings,
                )

    assert asyncio.run(run_scan("automation-scan-below")) is True
    with app.state.database.session_factory() as db:
        first_job = db.get(SyncJob, UUID(first_job_id))
        assert first_job.result["qualified_contents"] == 0
        assert first_job.result["analyses_queued"] == 0
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 0
        assert db.scalar(select(func.count()).select_from(WorkspaceInspiration)) == 0
        for fetch in db.scalars(select(ProviderFetch)).all():
            fetch.fresh_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        for snapshot in db.scalars(select(ContentMetricSnapshot)).all():
            snapshot.captured_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    should_pass = True
    second_job_id = client.post(
        f"/api/v1/tracked-profiles/{profile['id']}/sync",
        headers=headers,
    ).json()["data"]["job_id"]
    assert asyncio.run(run_scan("automation-scan-above")) is True
    with app.state.database.session_factory() as db:
        second_job = db.get(SyncJob, UUID(second_job_id))
        assert second_job.result["qualified_contents"] == 1
        assert second_job.result["analyses_queued"] == 1
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 1
        assert db.scalar(select(func.count()).select_from(WorkspaceInspiration)) == 1
        latest = db.scalar(
            select(ContentScore)
            .join(ExternalContent, ExternalContent.id == ContentScore.external_content_id)
            .where(ExternalContent.external_id == "68b39115000000001c037dad")
            .order_by(ContentScore.calculated_at.desc(), ContentScore.id.desc())
            .limit(1)
        )
        assert latest.grade == "qualified"
        assert latest.evidence["automation_gate"]["passed"] is True
        assert latest.evidence["score_mode"] == "hard_threshold"

    today = client.get("/api/v1/automation/today", headers=headers)
    assert today.status_code == 200
    summary = today.json()["data"]
    assert summary["scanned_profiles"] == 1
    assert summary["qualified_contents"] == 1
    assert summary["l1_queued"] == 1
    assert len(summary["candidates"]) == 1
    assert summary["candidates"][0]["grade"] == "qualified"
    assert summary["candidates"][0]["score_mode"] == "hard_threshold"
