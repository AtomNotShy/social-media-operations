import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, ExternalContent, SyncJob, Transcript
from app.jobs.errors import JobExecutionError
from app.modules.analysis.budget import settle_ai_budget
from app.modules.analysis.schemas import AnalysisL1Result, AnalysisL2Result
from app.providers.ai.base import AnalysisProvider


class AnalysisHandler:
    def __init__(self, db: Session, provider: AnalysisProvider | None) -> None:
        self.db = db
        self.provider = provider

    async def handle(self, job: SyncJob) -> dict:
        run_id = self._payload_run_id(job)
        run = self.db.scalar(
            select(AnalysisRun).where(
                AnalysisRun.id == run_id,
                AnalysisRun.workspace_id == job.workspace_id,
            )
        )
        if run is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Analysis run no longer exists.",
                retryable=False,
            )
        if self.provider is None:
            self._fail(run, "AI_NOT_CONFIGURED", "No AI provider is configured.")
            raise JobExecutionError(
                code="AI_NOT_CONFIGURED",
                message="No AI provider is configured.",
                retryable=False,
            )
        content = self.db.scalar(
            select(ExternalContent).where(
                ExternalContent.id == run.external_content_id,
                ExternalContent.workspace_id == job.workspace_id,
            )
        )
        if content is None:
            self._fail(run, "NOT_FOUND", "Source content no longer exists.")
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Source content no longer exists.",
                retryable=False,
            )
        transcript = self.db.scalar(
            select(Transcript)
            .where(
                Transcript.workspace_id == job.workspace_id,
                Transcript.external_content_id == content.id,
                Transcript.status == "succeeded",
            )
            .order_by(Transcript.finished_at.desc(), Transcript.created_at.desc())
            .limit(1)
        )
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.error_code = None
        run.error_message = None
        self.db.commit()
        try:
            output = await self.provider.analyze(
                run=run,
                content=content,
                transcript=transcript,
            )
            schema = AnalysisL1Result if run.analysis_level == "l1" else AnalysisL2Result
            validated = schema.model_validate(output.result)
            evidence_refs = sorted(set(output.evidence_refs))
            if f"content:{content.id}" not in evidence_refs:
                raise JobExecutionError(
                    code="AI_EVIDENCE_INVALID",
                    message="Analysis output does not cite its source content.",
                    retryable=False,
                )
        except ValidationError as exc:
            self._fail(run, "AI_OUTPUT_INVALID", "AI output failed schema validation.")
            raise JobExecutionError(
                code="AI_OUTPUT_INVALID",
                message="AI output failed schema validation.",
                retryable=False,
            ) from exc
        except JobExecutionError as exc:
            self._fail(run, exc.code, exc.message)
            raise
        except Exception as exc:
            self._fail(run, "AI_PROVIDER_ERROR", "AI provider request failed.")
            raise JobExecutionError(
                code="AI_PROVIDER_ERROR",
                message="AI provider request failed.",
                retryable=True,
            ) from exc

        run.result = validated.model_dump(mode="json")
        run.evidence_refs = evidence_refs
        run.input_tokens = output.input_tokens
        run.output_tokens = output.output_tokens
        run.cost_usd = output.cost_usd
        run.latency_ms = output.latency_ms
        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        settle_ai_budget(
            self.db,
            sync_job_id=job.id,
            actual_cost_usd=output.cost_usd,
        )
        self.db.commit()
        return {
            "analysis_run_id": str(run.id),
            "analysis_level": run.analysis_level,
            "evidence_refs": evidence_refs,
        }

    def _fail(self, run: AnalysisRun, code: str, message: str) -> None:
        run.status = "failed"
        run.error_code = code
        run.error_message = message
        run.finished_at = datetime.now(timezone.utc)
        self.db.commit()

    @staticmethod
    def _payload_run_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["analysis_run_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="AI_ANALYSIS job is missing analysis_run_id.",
                retryable=False,
            ) from exc
