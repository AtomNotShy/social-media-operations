import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    ContentPackage,
    ContentProject,
    GenerationRun,
    ReviewInsight,
    ScriptVersion,
    SyncJob,
)
from app.jobs.errors import JobExecutionError
from app.modules.analysis.budget import (
    close_ai_attempt,
    open_ai_attempt,
    settle_ai_budget,
)
from app.modules.content_packages.schemas import GeneratedContentPackageResult
from app.modules.generation.schemas import GeneratedReviewResult, GeneratedScriptResult
from app.providers.ai.base import AIProviderRequestError
from app.providers.ai.factory import generation_provider_for_run
from app.providers.ai.generation import ContentGenerationProvider


class GenerationHandler:
    def __init__(
        self,
        db: Session,
        provider: ContentGenerationProvider | None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings

    async def handle(self, job: SyncJob) -> dict:
        run_id = self._payload_run_id(job)
        run = self.db.scalar(
            select(GenerationRun).where(
                GenerationRun.id == run_id,
                GenerationRun.workspace_id == job.workspace_id,
            )
        )
        if run is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Generation run no longer exists.",
                retryable=False,
            )
        if run.status == "succeeded":
            # A previous attempt already produced and persisted the output but
            # its job commit may have been lost.  Reuse the committed result
            # instead of calling the provider again (idempotency for retries).
            return {
                "generation_run_id": str(run.id),
                "generation_type": run.generation_type,
                "created_resource_id": (
                    str(run.result["created_resource_id"])
                    if run.result and run.result.get("created_resource_id")
                    else None
                ),
                "evidence_refs": run.evidence_refs,
                "reused": True,
            }
        provider = self.provider
        if provider is None and self.settings is not None:
            try:
                provider = generation_provider_for_run(
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
            self._fail(run, "AI_NOT_CONFIGURED", "No content generation provider is configured.")
            raise JobExecutionError(
                code="AI_NOT_CONFIGURED",
                message="No content generation provider is configured.",
                retryable=False,
            )
        if run.generation_type in {"script_draft", "content_package"}:
            try:
                self._validate_project_version(run)
            except JobExecutionError as exc:
                self._fail(run, exc.code, exc.message)
                raise
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.error_code = None
        run.error_message = None
        open_ai_attempt(
            self.db,
            workspace_id=run.workspace_id,
            run_type="generation",
            run_id=run.id,
            sync_job_id=job.id,
            attempt_no=job.attempt,
            provider=run.model_provider,
            model=run.model,
        )
        self.db.commit()
        try:
            output = await provider.generate(run=run)
            schema = {
                "script_draft": GeneratedScriptResult,
                "review_summary": GeneratedReviewResult,
                "content_package": GeneratedContentPackageResult,
            }.get(run.generation_type, GeneratedReviewResult)
            validated = schema.model_validate(output.result)
            evidence_refs = sorted(set(output.evidence_refs))
            if not set(run.evidence_refs).issubset(evidence_refs):
                raise JobExecutionError(
                    code="AI_EVIDENCE_INVALID",
                    message="Generation output omitted required source evidence.",
                    retryable=False,
                )
            if run.generation_type == "script_draft":
                resource_id = self._persist_script(run, validated)
            elif run.generation_type == "content_package":
                resource_id = self._persist_content_package(run, validated)
            else:
                resource_id = self._persist_review(run, validated)
        except ValidationError as exc:
            self._fail(
                run,
                "AI_OUTPUT_INVALID",
                "AI output failed schema validation.",
                sync_job_id=job.id,
                attempt_no=job.attempt,
            )
            raise JobExecutionError(
                code="AI_OUTPUT_INVALID",
                message="AI output failed schema validation.",
                retryable=False,
            ) from exc
        except JobExecutionError as exc:
            self._fail(
                run,
                exc.code,
                exc.message,
                sync_job_id=job.id,
                attempt_no=job.attempt,
            )
            raise
        except AIProviderRequestError as exc:
            self._fail(
                run,
                exc.code,
                exc.message,
                sync_job_id=job.id,
                attempt_no=job.attempt,
            )
            raise JobExecutionError(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            ) from exc
        except Exception as exc:
            self._fail(
                run,
                "AI_PROVIDER_ERROR",
                "AI generation request failed.",
                sync_job_id=job.id,
                attempt_no=job.attempt,
            )
            raise JobExecutionError(
                code="AI_PROVIDER_ERROR",
                message="AI generation request failed.",
                retryable=True,
            ) from exc

        run.result = {
            **validated.model_dump(mode="json"),
            "created_resource_id": str(resource_id),
        }
        run.evidence_refs = evidence_refs
        run.input_tokens = output.input_tokens
        run.output_tokens = output.output_tokens
        run.cost_usd = output.cost_usd
        run.latency_ms = output.latency_ms
        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        close_ai_attempt(
            self.db,
            sync_job_id=job.id,
            attempt_no=job.attempt,
            status="succeeded",
            input_tokens=output.input_tokens,
            output_tokens=output.output_tokens,
            cost_usd=output.cost_usd,
            latency_ms=output.latency_ms,
        )
        settle_ai_budget(
            self.db,
            sync_job_id=job.id,
            actual_cost_usd=output.cost_usd,
        )
        self.db.commit()
        return {
            "generation_run_id": str(run.id),
            "generation_type": run.generation_type,
            "created_resource_id": str(resource_id),
            "evidence_refs": evidence_refs,
        }

    def _validate_project_version(self, run: GenerationRun) -> None:
        project = self.db.scalar(
            select(ContentProject).where(
                ContentProject.workspace_id == run.workspace_id,
                ContentProject.id == run.content_project_id,
            )
        )
        if project is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Content project no longer exists.",
                retryable=False,
            )
        if project.version != run.input_payload.get("project_version"):
            raise JobExecutionError(
                code="VERSION_CONFLICT",
                message="Content project changed before generation started.",
                retryable=False,
            )

    def _persist_script(
        self,
        run: GenerationRun,
        result: GeneratedScriptResult,
    ) -> uuid.UUID:
        project = self.db.scalar(
            select(ContentProject)
            .where(
                ContentProject.workspace_id == run.workspace_id,
                ContentProject.id == run.content_project_id,
            )
            .with_for_update()
        )
        if project is None or project.version != run.input_payload.get("project_version"):
            raise JobExecutionError(
                code="VERSION_CONFLICT",
                message="Content project changed while the generated script was in flight.",
                retryable=False,
            )
        latest_version = self.db.scalar(
            select(func.max(ScriptVersion.version_no)).where(
                ScriptVersion.content_project_id == project.id
            )
        )
        script = ScriptVersion(
            workspace_id=run.workspace_id,
            content_project_id=project.id,
            version_no=(latest_version or 0) + 1,
            body=result.body,
            structured_body=result.structured_body,
            change_note="AI generated draft",
            created_by=uuid.UUID(run.input_payload["requested_by"]),
            generation_run_id=run.id,
        )
        self.db.add(script)
        self.db.flush()
        project.version += 1
        if project.status == "idea":
            project.status = "scripting"
        return script.id

    def _persist_content_package(
        self,
        run: GenerationRun,
        result: GeneratedContentPackageResult,
    ) -> uuid.UUID:
        package = ContentPackage(
            workspace_id=run.workspace_id,
            content_project_id=run.content_project_id,
            script_version_id=uuid.UUID(str(run.input_payload["script"]["id"])),
            generation_run_id=run.id,
            schema_version=result.schema_version,
            target_platform=result.target_platform,
            status="draft",
            version=1,
            package=result.model_dump(mode="json"),
            evidence_refs=sorted(set(result.evidence_refs)),
            created_by=uuid.UUID(str(run.input_payload["requested_by"])),
        )
        self.db.add(package)
        self.db.flush()
        return package.id

    def _persist_review(
        self,
        run: GenerationRun,
        result: GeneratedReviewResult,
    ) -> uuid.UUID:
        if run.publish_record_id is None:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="Review generation is missing its publish record.",
                retryable=False,
            )
        review = ReviewInsight(
            workspace_id=run.workspace_id,
            publish_record_id=run.publish_record_id,
            review_window=run.input_payload["review_window"],
            metrics=run.input_payload["metrics"],
            analysis=result.analysis,
            next_actions=result.next_actions,
            created_by=uuid.UUID(run.input_payload["requested_by"]),
        )
        self.db.add(review)
        self.db.flush()
        project = self.db.get(ContentProject, run.content_project_id)
        if project is not None and project.status == "published":
            project.status = "reviewing"
            project.version += 1
        return review.id

    def _fail(
        self,
        run: GenerationRun,
        code: str,
        message: str,
        *,
        sync_job_id: uuid.UUID | None = None,
        attempt_no: int | None = None,
    ) -> None:
        run.status = "failed"
        run.error_code = code
        run.error_message = message
        run.finished_at = datetime.now(timezone.utc)
        if sync_job_id is not None and attempt_no is not None:
            close_ai_attempt(
                self.db,
                sync_job_id=sync_job_id,
                attempt_no=attempt_no,
                status="failed",
                error_code=code,
                error_message=message,
            )
        self.db.commit()

    @staticmethod
    def _payload_run_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["generation_run_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="CONTENT_GENERATION job is missing generation_run_id.",
                retryable=False,
            ) from exc
