from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import ExternalContent, SyncJob, Workspace
from app.modules.ai_connections.service import configured_for
from app.modules.analysis.service import request_analysis
from app.modules.inspirations.service import upsert_external_content
from app.modules.scoring.service import calculate_content_score
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.platforms import get_platform_binding
from app.providers.social.tikhub.registry import get_endpoint

FALLBACK_DETAIL_ERROR_CODES = {
    "PROVIDER_ERROR",
    "PROVIDER_REQUEST_INVALID",
    "SOURCE_CONTENT_UNAVAILABLE",
}


class ContentDetailHandler:
    def __init__(
        self,
        db: Session,
        gateway: TikHubGateway,
        adapter: Any | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.adapter = adapter
        self.settings = settings

    async def handle(self, job: SyncJob) -> dict:
        workspace = self.db.get(Workspace, job.workspace_id)
        if workspace is None:
            raise TikHubError(
                code="NOT_FOUND",
                message="Workspace no longer exists.",
                retryable=False,
            )
        platform = str(job.payload.get("platform") or "")
        try:
            binding = get_platform_binding(platform)
        except ValueError as exc:
            raise TikHubError(
                code="UNSUPPORTED_PLATFORM_CAPABILITY",
                message=f"Content detail import is not implemented for {platform}.",
                retryable=False,
            ) from exc
        adapter = self.adapter or binding.adapter
        external_id = job.payload.get("external_id")
        canonical_url = str(job.payload.get("canonical_url") or job.payload.get("share_text") or "")
        params = binding.detail_params(
            external_id if isinstance(external_id, str) and external_id else None,
            canonical_url,
        )
        if not any(params.values()):
            raise TikHubError(
                code="JOB_PAYLOAD_INVALID",
                message="CONTENT_DETAIL_FETCH requires an external ID or canonical URL.",
                retryable=False,
            )

        endpoint_key = binding.detail_endpoint
        try:
            if platform == "xiaohongshu":
                try:
                    result = await self._fetch_and_persist(
                        workspace=workspace,
                        endpoint=get_endpoint(endpoint_key),
                        params=params,
                        sync_job_id=job.id,
                    )
                    content_type = "image_text"
                except TikHubError as exc:
                    if exc.code not in FALLBACK_DETAIL_ERROR_CODES:
                        raise
                    endpoint_key = "xhs.content_video_detail"
                    result = await self._fetch_and_persist(
                        workspace=workspace,
                        endpoint=get_endpoint(endpoint_key),
                        params=params,
                        sync_job_id=job.id,
                    )
                    content_type = "video"
            else:
                result = await self._fetch_and_persist(
                    workspace=workspace,
                    endpoint=get_endpoint(endpoint_key),
                    params=params,
                    sync_job_id=job.id,
                )
                content_type = "video"
        except TikHubError as exc:
            if exc.code == "SOURCE_CONTENT_UNAVAILABLE":
                self._mark_source_unavailable(
                    workspace_id=workspace.id,
                    platform=platform,
                    external_id=external_id,
                    canonical_url=canonical_url,
                )
                self.db.commit()
            raise

        item = adapter.parse_content_detail(
            result.payload,
            content_type=content_type,
            fallback_external_id=external_id if isinstance(external_id, str) else None,
        )
        content, inspiration, created = upsert_external_content(
            self.db,
            workspace_id=workspace.id,
            item=item,
            provider_fetch_id=result.provider_fetch_id,
            source="manual_url",
            detail_status="detail",
        )
        self.db.commit()
        score_id = None
        score_grade = None
        score_error = None
        try:
            score = calculate_content_score(
                self.db,
                workspace_id=workspace.id,
                content_id=content.id,
            )
            self.db.commit()
            score_id = str(score.id)
            score_grade = score.grade
        except AppError as exc:
            self.db.rollback()
            score_error = exc.code

        analysis_run_id = None
        analysis_status = "not_requested"
        if job.payload.get("analyze"):
            if (
                self.settings is None
                or not configured_for(
                    self.db,
                    workspace_id=workspace.id,
                    task_type="l1",
                    settings=self.settings,
                )
            ):
                analysis_status = "not_configured"
            else:
                run, reused = request_analysis(
                    self.db,
                    workspace_id=workspace.id,
                    inspiration_id=inspiration.id,
                    level="l1",
                    force=False,
                    settings=self.settings,
                )
                self.db.commit()
                analysis_run_id = str(run.id)
                analysis_status = "reused" if reused else "queued"
        return {
            "inspiration_id": str(inspiration.id),
            "external_content_id": str(content.id),
            "created": created,
            "endpoint_key": endpoint_key,
            "analysis_requested": bool(job.payload.get("analyze")),
            "analysis_status": analysis_status,
            "analysis_run_id": analysis_run_id,
            "score_id": score_id,
            "score_grade": score_grade,
            "score_error": score_error,
        }

    async def _fetch_and_persist(self, **kwargs):
        try:
            result = await self.gateway.fetch(**kwargs)
            self.db.commit()
            return result
        except TikHubError:
            self.db.commit()
            raise

    def _mark_source_unavailable(
        self,
        *,
        workspace_id,
        platform: str,
        external_id: object,
        canonical_url: str,
    ) -> None:
        identifiers = []
        if isinstance(external_id, str) and external_id:
            identifiers.append(ExternalContent.external_id == external_id)
        if canonical_url:
            identifiers.append(ExternalContent.canonical_url == canonical_url)
        if not identifiers:
            return
        contents = self.db.scalars(
            select(ExternalContent).where(
                ExternalContent.workspace_id == workspace_id,
                ExternalContent.platform == platform,
                or_(*identifiers),
            )
        ).all()
        now = datetime.now(timezone.utc)
        for content in contents:
            content.deleted_at_source = content.deleted_at_source or now
            content.media_manifest = []
