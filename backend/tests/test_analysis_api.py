import asyncio
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db.models import (
    AICostLedger,
    AnalysisRun,
    ContentScore,
    ExternalContent,
    ScoringPolicy,
    SyncJob,
    Workspace,
    WorkspaceInspiration,
)
from app.jobs.worker import process_one
from app.modules.analysis.schemas import AnalysisL1Result, AnalysisL2Result
from app.providers.ai.base import AnalysisProviderResult
from app.providers.ai.fixture import FixtureAnalysisProvider
from app.providers.asr.fixture import FixtureTranscriptProvider
from app.providers.social.tikhub.client import TikHubHttpClient


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _seed_video_inspiration(app, workspace):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="analysis-video",
            canonical_url="https://www.xiaohongshu.com/explore/analysis-video",
            content_type="video",
            title="A fixture video",
            body_text="Untrusted external content.",
            author_snapshot={},
            media_manifest=[{"type": "video", "url": "https://media.example.invalid/video.mp4"}],
            content_hash="content-version-1",
        )
        db.add(content)
        db.flush()
        inspiration = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=content.id,
            source="test",
        )
        db.add(inspiration)
        db.commit()
        return str(inspiration.id), content.id


def _seed_text_inspiration(app, workspace):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="analysis-text",
            canonical_url="https://www.xiaohongshu.com/explore/analysis-text",
            content_type="note",
            title="A text-only note",
            body_text="Pure text content without any video.",
            author_snapshot={},
            media_manifest=[],
            content_hash="content-version-text",
        )
        db.add(content)
        db.flush()
        inspiration = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=content.id,
            source="test",
        )
        db.add(inspiration)
        db.commit()
        return str(inspiration.id), content.id


def test_analysis_and_transcript_reject_unconfigured_providers(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_video_inspiration(app, workspace)
    headers = _headers(auth_headers, workspace)

    analysis = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l1"},
    )
    transcript = client.post(
        f"/api/v1/inspirations/{inspiration_id}/transcribe",
        headers=headers,
    )

    assert analysis.status_code == 409
    assert analysis.json()["code"] == "AI_NOT_CONFIGURED"
    assert transcript.status_code == 409
    assert transcript.json()["code"] == "ASR_NOT_CONFIGURED"


def test_transcript_rejects_text_only_content_before_asr_configuration(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_text_inspiration(app, workspace)
    headers = _headers(auth_headers, workspace)

    transcript = client.post(
        f"/api/v1/inspirations/{inspiration_id}/transcribe",
        headers=headers,
    )

    assert transcript.status_code == 409
    assert transcript.json()["code"] == "TRANSCRIPT_SOURCE_MISSING"


def test_analysis_and_transcript_requests_are_deduplicated(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_video_inspiration(app, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-l1"
    app.state.settings.asr_provider = "fixture"
    app.state.settings.asr_model = "fixture-asr"
    headers = _headers(auth_headers, workspace)

    first_analysis = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l1"},
    )
    second_analysis = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l1"},
    )
    first_transcript = client.post(
        f"/api/v1/inspirations/{inspiration_id}/transcribe",
        headers=headers,
    )
    second_transcript = client.post(
        f"/api/v1/inspirations/{inspiration_id}/transcribe",
        headers=headers,
    )

    assert first_analysis.status_code == 202
    assert second_analysis.status_code == 202
    assert first_analysis.json()["data"]["reused"] is False
    assert second_analysis.json()["data"]["reused"] is True
    assert first_analysis.json()["data"]["analysis"]["prompt_version"].endswith(
        ":zh-cn-v1"
    )
    assert (
        first_analysis.json()["data"]["analysis"]["id"]
        == second_analysis.json()["data"]["analysis"]["id"]
    )
    assert first_transcript.status_code == 202
    assert second_transcript.status_code == 202
    assert second_transcript.json()["data"]["reused"] is True
    with app.state.database.session_factory() as db:
        jobs = db.scalars(select(SyncJob)).all()
        assert sorted(job.job_type for job in jobs) == ["AI_ANALYSIS", "TRANSCRIBE"]
        ledgers = db.scalars(select(AICostLedger)).all()
        assert len(ledgers) == 2
        assert all(ledger.status == "reserved" for ledger in ledgers)


def test_ai_budget_is_reserved_before_job_can_spend(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_video_inspiration(app, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-l1"
    with app.state.database.session_factory() as db:
        current_workspace = db.get(Workspace, UUID(workspace["id"]))
        current_workspace.daily_ai_budget_usd = Decimal("0")
        db.commit()

    response = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=_headers(auth_headers, workspace),
        json={"level": "l1"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "ANALYSIS_BUDGET_EXCEEDED"
    with app.state.database.session_factory() as db:
        assert db.scalar(select(AICostLedger)) is None
        assert db.scalar(select(SyncJob)) is None


def test_l2_requires_high_value_score_and_recommending_l1(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, content_id = _seed_video_inspiration(app, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-l2"
    headers = _headers(auth_headers, workspace)

    rejected = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l2"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "L2_POLICY_REJECTED"

    with app.state.database.session_factory() as db:
        policy = db.scalar(
            select(ScoringPolicy).where(
                ScoringPolicy.workspace_id == UUID(workspace["id"]),
                ScoringPolicy.platform == "xiaohongshu",
            )
        )
        db.add(
            ContentScore(
                workspace_id=UUID(workspace["id"]),
                external_content_id=content_id,
                scoring_policy_id=policy.id,
                r_value=Decimal("5"),
                m_value=Decimal("0.2"),
                tier="micro",
                grade="t1",
                core_metric=Decimal("500"),
                baseline_value=Decimal("100"),
                is_initial=True,
                evidence={},
            )
        )
        db.add(
            AnalysisRun(
                workspace_id=UUID(workspace["id"]),
                external_content_id=content_id,
                analysis_level="l1",
                model_provider="fixture",
                model="fixture-l1",
                prompt_version="l1-v1",
                input_hash="successful-l1",
                status="succeeded",
                result={
                    "summary": "Summary",
                    "factors": [],
                    "confidence": 0.8,
                    "caveats": [],
                    "life": "evergreen",
                    "life_reason": "Reason",
                    "recommended_for_l2": True,
                },
                evidence_refs=[f"content:{content_id}"],
            )
        )
        db.commit()

    accepted = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l2"},
    )
    assert accepted.status_code == 202
    assert accepted.json()["data"]["analysis"]["analysis_level"] == "l2"


def test_analysis_result_schemas_are_strict():
    l1 = AnalysisL1Result.model_validate(
        {
            "summary": "Summary",
            "factors": ["Strong hook"],
            "confidence": 0.8,
            "caveats": [],
            "life": "evergreen",
            "life_reason": "Reusable advice",
            "recommended_for_l2": True,
        }
    )
    assert l1.life == "evergreen"
    with pytest.raises(ValidationError):
        AnalysisL1Result.model_validate(
            {
                "summary": "Summary",
                "factors": [],
                "confidence": 1.5,
                "caveats": [],
                "life": "forever",
                "life_reason": "Invalid enums and confidence",
                "recommended_for_l2": True,
                "unexpected": "not allowed",
            }
        )
    with pytest.raises(ValidationError):
        AnalysisL2Result.model_validate(
            {
                "hook": "Hook",
                "structure": [],
                "audience_pains": [],
                "triggers": [],
                "reusable_patterns": [],
                "non_reusable_context": [],
                "topic_ideas": [],
                "recommended_channels": [],
                "risks": [],
                "fact_checks": [],
                "evidence_refs": [],
            }
        )


def test_worker_persists_validated_analysis_and_timed_transcript(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_video_inspiration(app, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-l1"
    app.state.settings.asr_provider = "fixture"
    app.state.settings.asr_model = "fixture-asr"
    headers = _headers(auth_headers, workspace)
    analysis_id = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l1"},
    ).json()["data"]["analysis"]["id"]
    transcript_id = client.post(
        f"/api/v1/inspirations/{inspiration_id}/transcribe",
        headers=headers,
    ).json()["data"]["transcript"]["id"]

    async def run_jobs():
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
            for _ in range(2):
                with app.state.database.session_factory() as db:
                    assert await process_one(
                        db,
                        client=provider_client,
                        worker_id="analysis-worker",
                        analysis_provider=FixtureAnalysisProvider(),
                        transcript_provider=FixtureTranscriptProvider(),
                    )

    asyncio.run(run_jobs())

    analysis = client.get(f"/api/v1/analyses/{analysis_id}", headers=headers)
    transcript = client.get(f"/api/v1/transcripts/{transcript_id}", headers=headers)
    assert analysis.json()["data"]["status"] == "succeeded"
    assert analysis.json()["data"]["result"]["recommended_for_l2"] is True
    assert analysis.json()["data"]["evidence_refs"]
    assert transcript.json()["data"]["status"] == "succeeded"
    assert transcript.json()["data"]["segments"] == [
        {
            "start_ms": 0,
            "end_ms": 1000,
            "text": "Untrusted external content.",
        }
    ]
    with app.state.database.session_factory() as db:
        ledgers = db.scalars(select(AICostLedger)).all()
        assert len(ledgers) == 2
        assert all(ledger.status == "settled" for ledger in ledgers)
        assert all(ledger.actual_cost_usd == 0 for ledger in ledgers)


def test_worker_rejects_invalid_ai_output(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id, _ = _seed_video_inspiration(app, workspace)
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-l1"
    headers = _headers(auth_headers, workspace)
    accepted = client.post(
        f"/api/v1/inspirations/{inspiration_id}/analyze",
        headers=headers,
        json={"level": "l1"},
    ).json()["data"]["analysis"]

    class InvalidProvider:
        async def analyze(self, **kwargs):
            return AnalysisProviderResult(
                result={"summary": "missing required fields"},
                evidence_refs=[f"content:{accepted['external_content_id']}"],
            )

    async def run_job():
        async with httpx.AsyncClient() as http_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="unused",
                client=http_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id="invalid-analysis-worker",
                    analysis_provider=InvalidProvider(),
                )

    assert asyncio.run(run_job()) is True
    response = client.get(f"/api/v1/analyses/{accepted['id']}", headers=headers)
    assert response.json()["data"]["status"] == "failed"
    assert response.json()["data"]["error_code"] == "AI_OUTPUT_INVALID"
    with app.state.database.session_factory() as db:
        job = db.get(SyncJob, UUID(accepted["sync_job_id"]))
        assert job.status == "dead"
        assert job.last_error_code == "AI_OUTPUT_INVALID"
