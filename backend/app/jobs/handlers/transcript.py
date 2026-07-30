import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExternalContent, SyncJob, Transcript
from app.jobs.errors import JobExecutionError
from app.modules.analysis.budget import settle_ai_budget
from app.providers.asr.base import TranscriptProvider


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)


class TranscriptHandler:
    def __init__(self, db: Session, provider: TranscriptProvider | None) -> None:
        self.db = db
        self.provider = provider

    async def handle(self, job: SyncJob) -> dict:
        transcript_id = self._payload_transcript_id(job)
        transcript = self.db.scalar(
            select(Transcript).where(
                Transcript.id == transcript_id,
                Transcript.workspace_id == job.workspace_id,
            )
        )
        if transcript is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Transcript no longer exists.",
                retryable=False,
            )
        if self.provider is None:
            self._fail(transcript, "ASR_NOT_CONFIGURED", "No ASR provider is configured.")
            raise JobExecutionError(
                code="ASR_NOT_CONFIGURED",
                message="No ASR provider is configured.",
                retryable=False,
            )
        try:
            content = self.db.scalar(
                select(ExternalContent).where(
                    ExternalContent.id == transcript.external_content_id,
                    ExternalContent.workspace_id == job.workspace_id,
                )
            )
            media_url = self._media_url(content)
        except JobExecutionError as exc:
            self._fail(transcript, exc.code, exc.message)
            raise
        transcript.status = "running"
        transcript.started_at = datetime.now(timezone.utc)
        transcript.error_code = None
        transcript.error_message = None
        self.db.commit()
        try:
            output = await self.provider.transcribe(
                transcript=transcript,
                content=content,
                media_url=media_url,
            )
            segments = [TranscriptSegment.model_validate(item) for item in output.segments]
            if not output.text.strip():
                raise ValueError("Transcript text is empty")
            previous_end = 0
            for segment in segments:
                if segment.end_ms <= segment.start_ms or segment.start_ms < previous_end:
                    raise ValueError("Transcript segments overlap or have invalid bounds")
                previous_end = segment.end_ms
        except (ValidationError, ValueError) as exc:
            self._fail(transcript, "ASR_OUTPUT_INVALID", "ASR output failed validation.")
            raise JobExecutionError(
                code="ASR_OUTPUT_INVALID",
                message="ASR output failed validation.",
                retryable=False,
            ) from exc
        except Exception as exc:
            self._fail(transcript, "ASR_PROVIDER_ERROR", "ASR provider request failed.")
            raise JobExecutionError(
                code="ASR_PROVIDER_ERROR",
                message="ASR provider request failed.",
                retryable=True,
            ) from exc

        transcript.text = output.text
        transcript.segments = [segment.model_dump() for segment in segments]
        transcript.language = output.language
        transcript.confidence = output.confidence
        transcript.cost_usd = output.cost_usd
        transcript.status = "succeeded"
        transcript.finished_at = datetime.now(timezone.utc)
        settle_ai_budget(
            self.db,
            sync_job_id=job.id,
            actual_cost_usd=output.cost_usd,
        )
        self.db.commit()
        return {
            "transcript_id": str(transcript.id),
            "segment_count": len(segments),
        }

    def _fail(self, transcript: Transcript, code: str, message: str) -> None:
        transcript.status = "failed"
        transcript.error_code = code
        transcript.error_message = message
        transcript.finished_at = datetime.now(timezone.utc)
        self.db.commit()

    @staticmethod
    def _media_url(content: ExternalContent | None) -> str:
        if content is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Source content no longer exists.",
                retryable=False,
            )
        for item in content.media_manifest:
            if isinstance(item, dict) and item.get("type") == "video" and item.get("url"):
                return str(item["url"])
        raise JobExecutionError(
            code="TRANSCRIPT_SOURCE_MISSING",
            message="Source content has no video media.",
            retryable=False,
        )

    @staticmethod
    def _payload_transcript_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["transcript_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="TRANSCRIBE job is missing transcript_id.",
                retryable=False,
            ) from exc
