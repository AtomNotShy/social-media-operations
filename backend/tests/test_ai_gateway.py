import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import (
    AnalysisRun,
    ExternalContent,
    ProviderCircuitState,
    Workspace,
)
from app.jobs.service import create_job
from app.jobs.worker import AI_JOB_TYPES, process_one
from app.modules.analysis.budget import reserve_ai_budget
from app.providers.ai.base import AIProviderRequestError, AnalysisProviderResult
from app.providers.ai.fixture import FixtureAnalysisProvider
from app.providers.ai.gateway import AIGateway


class _FakeProvider:
    def __init__(self, errors: list[AIProviderRequestError | None] | None = None) -> None:
        self.errors = list(errors or [])
        self.calls = 0
        self.successes = 0

    async def analyze(self, **kwargs):
        self.calls += 1
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        self.successes += 1
        return AnalysisProviderResult(result={}, evidence_refs=[])


def _gateway(app, workspace, *, conn_id=None, threshold=4, open_seconds=60, rpm=0, provider=None):
    with app.state.database.session_factory() as db:
        fake = provider or _FakeProvider()
        gateway = AIGateway(
            fake,
            db=db,
            workspace_id=uuid.UUID(workspace["id"]),
            connection_id=conn_id or uuid.uuid4(),
            model="deepseek-v4-flash",
            circuit_failure_threshold=threshold,
            circuit_open_seconds=open_seconds,
            rate_limit_rpm=rpm,
        )
        return fake, gateway, db


def test_gateway_opens_circuit_after_threshold_and_blocks_retries(app, workspace):
    fake = _FakeProvider(
        errors=[
            AIProviderRequestError("AI_PROVIDER_UNAVAILABLE", "upstream down", retryable=True)
        ]
        * 4
    )

    async def run():
        with app.state.database.session_factory() as db:
            gateway = AIGateway(
                fake,
                db=db,
                workspace_id=uuid.UUID(workspace["id"]),
                connection_id=uuid.uuid4(),
                model="deepseek-v4-flash",
                circuit_failure_threshold=4,
                circuit_open_seconds=60,
            )
            for _ in range(4):
                try:
                    await gateway.analyze()
                except AIProviderRequestError:
                    pass
            circuit = db.scalar(
                select(ProviderCircuitState).where(
                    ProviderCircuitState.workspace_id == uuid.UUID(workspace["id"])
                )
            )
            assert circuit.state == "open"
            with pytest.raises(AIProviderRequestError) as excinfo:
                await gateway.analyze()
            assert excinfo.value.code == "AI_CIRCUIT_OPEN"
            assert excinfo.value.retryable is True
            assert fake.calls == 4

            # Let the breaker half-open; a successful probe closes it again.
            circuit.retry_after = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
            await gateway.analyze()
            assert fake.successes == 1
            circuit = db.scalar(
                select(ProviderCircuitState).where(
                    ProviderCircuitState.workspace_id == uuid.UUID(workspace["id"])
                )
            )
            assert circuit.state == "closed"
            assert circuit.consecutive_failures == 0

    asyncio.run(run())


def test_gateway_auth_failure_opens_circuit_immediately(app, workspace):
    fake = _FakeProvider(
        errors=[
            AIProviderRequestError("AI_AUTH_FAILED", "credentials rejected", retryable=False)
        ]
    )

    async def run():
        with app.state.database.session_factory() as db:
            gateway = AIGateway(
                fake,
                db=db,
                workspace_id=uuid.UUID(workspace["id"]),
                connection_id=uuid.uuid4(),
                model="deepseek-v4-flash",
            )
            with pytest.raises(AIProviderRequestError):
                await gateway.analyze()
            circuit = db.scalar(select(ProviderCircuitState))
            assert circuit.state == "open"
            assert circuit.last_error_code == "AI_AUTH_FAILED"

    asyncio.run(run())


def test_gateway_blocks_when_workspace_calls_are_paused(app, workspace):
    fake = _FakeProvider()

    async def run():
        with app.state.database.session_factory() as db:
            current = db.get(Workspace, uuid.UUID(workspace["id"]))
            current.settings = {**current.settings, "external_calls": {"paused": True}}
            db.commit()
            gateway = AIGateway(
                fake,
                db=db,
                workspace_id=uuid.UUID(workspace["id"]),
                connection_id=uuid.uuid4(),
                model="deepseek-v4-flash",
            )
            with pytest.raises(AIProviderRequestError) as excinfo:
                await gateway.analyze()
            assert excinfo.value.code == "AI_CALLS_PAUSED"
            assert fake.calls == 0

    asyncio.run(run())


def test_gateway_rate_limits_per_connection(app, workspace):
    fake = _FakeProvider()
    conn_id = uuid.uuid4()

    async def run():
        with app.state.database.session_factory() as db:
            gateway = AIGateway(
                fake,
                db=db,
                workspace_id=uuid.UUID(workspace["id"]),
                connection_id=conn_id,
                model="deepseek-v4-flash",
                rate_limit_rpm=1,
            )
            await gateway.analyze()
            with pytest.raises(AIProviderRequestError) as excinfo:
                await gateway.analyze()
            assert excinfo.value.code == "AI_RATE_LIMITED_LOCAL"
            assert fake.calls == 1

    asyncio.run(run())


def test_worker_without_tikhub_claims_only_ai_jobs(app, workspace):
    workspace_id = uuid.UUID(workspace["id"])
    content = ExternalContent(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        platform="xiaohongshu",
        external_id="ai-only-worker",
        canonical_url="https://www.xiaohongshu.com/explore/ai-only-worker",
        content_type="note",
        title="AI-only worker",
        body_text="Body",
        author_snapshot={},
        media_manifest=[],
    )
    analysis_run = AnalysisRun(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        external_content_id=content.id,
        analysis_level="l1",
        model_provider="fixture",
        model="fixture",
        prompt_version="l1-v1",
        input_hash="ai-only-worker",
        evidence_refs=[f"content:{content.id}"],
    )

    async def run():
        with app.state.database.session_factory() as db:
            db.add_all([content, analysis_run])
            profile_job, _ = create_job(
                db,
                workspace_id=workspace_id,
                job_type="PROFILE_SCAN",
                dedupe_key="ai-worker:profile",
                payload={},
            )
            ai_job, _ = create_job(
                db,
                workspace_id=workspace_id,
                job_type="AI_ANALYSIS",
                dedupe_key="ai-worker:analysis",
                payload={"analysis_run_id": str(analysis_run.id)},
            )
            reserve_ai_budget(
                db,
                workspace_id=workspace_id,
                sync_job_id=ai_job.id,
                resource_type="analysis",
                resource_id=analysis_run.id,
                provider="fixture",
                model="fixture",
                estimated_cost_usd=0,
            )
            db.commit()
            processed = await process_one(
                db,
                client=None,
                worker_id="ai-only-worker",
                job_types=AI_JOB_TYPES,
                analysis_provider=FixtureAnalysisProvider(),
                settings=app.state.settings,
            )
            assert processed is True
            db.refresh(profile_job)
            db.refresh(ai_job)
            assert profile_job.status == "pending"
            assert ai_job.status == "succeeded"
            analysis_run_id = analysis_run.id
            db.commit()
            return analysis_run_id

    asyncio.run(run())
