import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    AnalysisRun,
    ContentMetricSnapshot,
    ExternalContent,
    SyncJob,
    Transcript,
    Workspace,
    WorkspaceInspiration,
)
from app.jobs.errors import JobExecutionError
from app.modules.ai_connections.service import configured_for
from app.modules.analysis.budget import settle_ai_budget
from app.modules.analysis.schemas import AnalysisL1Result, AnalysisL2Result
from app.modules.analysis.service import request_analysis
from app.modules.automation.service import (
    get_automation_settings,
    within_daily_analysis_limit,
)
from app.providers.ai.base import AIProviderRequestError, AnalysisProvider
from app.providers.ai.factory import analysis_provider_for_run


class AnalysisHandler:
    def __init__(
        self,
        db: Session,
        provider: AnalysisProvider | None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings

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
        provider = self.provider
        if provider is None and self.settings is not None:
            try:
                provider = analysis_provider_for_run(
                    self.db,
                    run=run,
                    settings=self.settings,
                )
            except AppError as exc:
                self._fail(run, exc.code, exc.detail)
                raise JobExecutionError(
                    code=exc.code,
                    message=exc.detail,
                    retryable=exc.retryable,
                ) from exc
        if provider is None:
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
        metric_snapshot = self.db.scalar(
            select(ContentMetricSnapshot)
            .where(
                ContentMetricSnapshot.workspace_id == job.workspace_id,
                ContentMetricSnapshot.external_content_id == content.id,
            )
            .order_by(
                ContentMetricSnapshot.captured_at.desc(),
                ContentMetricSnapshot.created_at.desc(),
            )
            .limit(1)
        )
        metrics = (
            {
                "views": metric_snapshot.views,
                "likes": metric_snapshot.likes,
                "comments": metric_snapshot.comments,
                "favorites": metric_snapshot.favorites,
                "shares": metric_snapshot.shares,
                "downloads": metric_snapshot.downloads,
                **metric_snapshot.metrics,
            }
            if metric_snapshot is not None
            else None
        )
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.error_code = None
        run.error_message = None
        self.db.commit()
        try:
            output = await provider.analyze(
                run=run,
                content=content,
                transcript=transcript,
                metrics=metrics,
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
        except AIProviderRequestError as exc:
            self._fail(run, exc.code, exc.message)
            raise JobExecutionError(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            ) from exc
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
        auto_l2_status = "not_applicable"
        auto_l2_run_id = None
        if run.analysis_level == "l1" and validated.recommended_for_l2:
            auto_l2_status, auto_l2_run_id = self._queue_automatic_l2(run)
        return {
            "analysis_run_id": str(run.id),
            "analysis_level": run.analysis_level,
            "evidence_refs": evidence_refs,
            "auto_l2_status": auto_l2_status,
            "auto_l2_run_id": auto_l2_run_id,
        }

    def _queue_automatic_l2(self, run: AnalysisRun) -> tuple[str, str | None]:
        if self.settings is None:
            return "not_configured", None
        workspace = self.db.get(Workspace, run.workspace_id)
        if workspace is None:
            return "workspace_missing", None
        automation = get_automation_settings(workspace)
        if not automation.enabled or not automation.auto_l2:
            return "disabled", None
        if not within_daily_analysis_limit(
            self.db, workspace=workspace, level="l2", policy=automation
        ):
            return "daily_limit_reached", None
        if not configured_for(
            self.db,
            workspace_id=workspace.id,
            task_type="l2",
            settings=self.settings,
        ):
            return "not_configured", None
        inspiration = self.db.scalar(
            select(WorkspaceInspiration).where(
                WorkspaceInspiration.workspace_id == workspace.id,
                WorkspaceInspiration.external_content_id == run.external_content_id,
            )
        )
        if inspiration is None:
            return "inspiration_missing", None
        try:
            l2, reused = request_analysis(
                self.db,
                workspace_id=workspace.id,
                inspiration_id=inspiration.id,
                level="l2",
                force=False,
                settings=self.settings,
            )
            self.db.commit()
            return ("reused" if reused else "queued"), str(l2.id)
        except AppError as exc:
            self.db.rollback()
            return exc.code.lower(), None

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
