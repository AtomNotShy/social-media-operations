from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.db.models import (
    AICostLedger,
    AnalysisRun,
    ExternalContent,
    ProviderUsageDaily,
    SyncJob,
    Transcript,
)


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_provider_usage_is_aggregated_and_workspace_scoped(
    client,
    app,
    auth_headers,
    workspace,
):
    other = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Other", "timezone": "UTC"},
    ).json()["data"]
    today = date.today()
    with app.state.database.session_factory() as db:
        db.add_all(
            [
                ProviderUsageDaily(
                    workspace_id=UUID(workspace["id"]),
                    usage_date=today,
                    provider="tikhub",
                    endpoint_key="xhs.profile",
                    request_count=2,
                    success_count=2,
                    billable_count=2,
                    estimated_cost_usd=Decimal("0.002"),
                ),
                ProviderUsageDaily(
                    workspace_id=UUID(other["id"]),
                    usage_date=today,
                    provider="tikhub",
                    endpoint_key="xhs.profile",
                    request_count=99,
                    success_count=99,
                    billable_count=99,
                    estimated_cost_usd=Decimal("99"),
                ),
            ]
        )
        db.commit()

    response = client.get("/api/v1/usage/provider", headers=_headers(auth_headers, workspace))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["request_count"] == 2
    assert data["estimated_cost_usd"] == "0.002000"
    assert len(data["items"]) == 1


def test_ai_and_asr_usage_are_aggregated_without_frontend_cost_math(
    client,
    app,
    auth_headers,
    workspace,
):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="usage-content",
            canonical_url="https://www.xiaohongshu.com/explore/usage-content",
            content_type="video",
            duration_ms=45_000,
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        db.add_all(
            [
                AnalysisRun(
                    workspace_id=workspace_id,
                    external_content_id=content.id,
                    analysis_level="l1",
                    model_provider="fixture",
                    model="fixture-model",
                    prompt_version="v1",
                    input_hash="ai-usage-input",
                    status="succeeded",
                    evidence_refs=[],
                    input_tokens=800,
                    output_tokens=240,
                    cost_usd=Decimal("0.012"),
                ),
                Transcript(
                    workspace_id=workspace_id,
                    external_content_id=content.id,
                    provider="fixture",
                    model="fixture-asr",
                    status="succeeded",
                    input_hash="asr-usage-input",
                    cost_usd=Decimal("0.008"),
                ),
            ]
        )
        db.commit()

    headers = _headers(auth_headers, workspace)
    ai = client.get("/api/v1/usage/ai", headers=headers)
    asr = client.get("/api/v1/usage/asr", headers=headers)

    assert ai.status_code == 200
    assert ai.json()["data"] == {
        "run_count": 1,
        "success_count": 1,
        "input_tokens": 800,
        "output_tokens": 240,
        "cost_usd": "0.012000",
    }
    assert asr.status_code == 200
    assert asr.json()["data"] == {
        "transcript_count": 1,
        "success_count": 1,
        "audio_duration_ms": 45_000,
        "cost_usd": "0.008000",
    }


def test_queue_health_reports_only_current_workspace(
    client,
    app,
    auth_headers,
    workspace,
):
    workspace_id = UUID(workspace["id"])
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    with app.state.database.session_factory() as db:
        db.add_all(
            [
                SyncJob(
                    workspace_id=workspace_id,
                    job_type="PROFILE_SCAN",
                    dedupe_key="pending",
                    payload={},
                ),
                SyncJob(
                    workspace_id=workspace_id,
                    job_type="PROFILE_SCAN",
                    dedupe_key="running-stale",
                    payload={},
                    status="running",
                    locked_at=stale_at,
                    heartbeat_at=stale_at,
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/system/queue-health",
        headers=_headers(auth_headers, workspace),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["counts"] == {"pending": 1, "running": 1}
    assert data["active_count"] == 2
    assert data["stale_running_count"] == 1
    assert data["oldest_active_created_at"] is not None


def test_ai_budget_usage_includes_reserved_and_settled_costs(
    client,
    app,
    auth_headers,
    workspace,
):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        reserved_job = SyncJob(
            workspace_id=workspace_id,
            job_type="AI_ANALYSIS",
            dedupe_key="budget-reserved",
            payload={},
        )
        settled_job = SyncJob(
            workspace_id=workspace_id,
            job_type="TRANSCRIBE",
            dedupe_key="budget-settled",
            payload={},
        )
        db.add_all([reserved_job, settled_job])
        db.flush()
        db.add_all(
            [
                AICostLedger(
                    workspace_id=workspace_id,
                    sync_job_id=reserved_job.id,
                    resource_type="analysis",
                    resource_id=reserved_job.id,
                    usage_date=date.today(),
                    provider="fixture",
                    model="fixture-l1",
                    status="reserved",
                    estimated_cost_usd=Decimal("0.05"),
                ),
                AICostLedger(
                    workspace_id=workspace_id,
                    sync_job_id=settled_job.id,
                    resource_type="transcript",
                    resource_id=settled_job.id,
                    usage_date=date.today(),
                    provider="fixture",
                    model="fixture-asr",
                    status="settled",
                    estimated_cost_usd=Decimal("0.10"),
                    actual_cost_usd=Decimal("0.08"),
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/usage/ai-budget",
        headers=_headers(auth_headers, workspace),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "ledger_count": 2,
        "reserved_count": 1,
        "settled_count": 1,
        "uncertain_count": 0,
        "reserved_cost_usd": "0.050000",
        "settled_cost_usd": "0.080000",
        "uncertain_cost_usd": "0.000000",
        "effective_cost_usd": "0.130000",
        "daily_budget_usd": "5.0000",
    }
