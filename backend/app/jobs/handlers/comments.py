import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CommentSample, ExternalContent, SyncJob, Workspace
from app.jobs.errors import JobExecutionError
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.platforms import get_platform_binding
from app.providers.social.tikhub.registry import get_endpoint


class CommentFetchHandler:
    def __init__(
        self,
        db: Session,
        gateway: TikHubGateway,
        adapter: Any | None = None,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.adapter = adapter

    async def handle(self, job: SyncJob) -> dict:
        content_id = self._payload_content_id(job)
        content = self.db.scalar(
            select(ExternalContent).where(
                ExternalContent.id == content_id,
                ExternalContent.workspace_id == job.workspace_id,
            )
        )
        workspace = self.db.get(Workspace, job.workspace_id)
        if content is None or workspace is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Content or workspace no longer exists.",
                retryable=False,
            )
        try:
            binding = get_platform_binding(content.platform)
        except ValueError as exc:
            raise JobExecutionError(
                code="UNSUPPORTED_PLATFORM_CAPABILITY",
                message=f"Comment sampling is not implemented for {content.platform}.",
                retryable=False,
            ) from exc
        adapter = self.adapter or binding.adapter
        max_pages = max(1, min(int(job.payload.get("max_pages", 1)), 3))
        sort_strategy = str(job.payload.get("sort_strategy", "latest_v2"))
        cursor: str | None = None
        index = 0
        page_area = "UNFOLDED"
        pages_fetched = 0
        created = 0
        updated = 0
        for _ in range(max_pages):
            try:
                result = await self.gateway.fetch(
                    workspace=workspace,
                    endpoint=get_endpoint(binding.comments_endpoint),
                    params={
                        **binding.comment_params(
                            content.external_id,
                            cursor,
                            20,
                            sort_strategy,
                        ),
                        **(
                            {"index": index, "pageArea": page_area}
                            if content.platform == "xiaohongshu"
                            else {}
                        ),
                    },
                    sync_job_id=job.id,
                )
                self.db.commit()
            except TikHubError:
                self.db.commit()
                raise
            page = adapter.parse_comments(result.payload)
            for item in page.items:
                sample = self.db.scalar(
                    select(CommentSample).where(
                        CommentSample.workspace_id == workspace.id,
                        CommentSample.external_content_id == content.id,
                        CommentSample.external_comment_id == item.external_id,
                    )
                )
                if sample is None:
                    sample = CommentSample(
                        workspace_id=workspace.id,
                        external_content_id=content.id,
                        external_comment_id=item.external_id,
                        parent_external_id=item.parent_external_id,
                        author_snapshot=item.author,
                        body_text=item.body_text,
                        like_count=item.like_count,
                        published_at=item.published_at,
                        provider_fetch_id=result.provider_fetch_id,
                    )
                    self.db.add(sample)
                    created += 1
                else:
                    sample.parent_external_id = item.parent_external_id
                    sample.author_snapshot = item.author
                    sample.body_text = item.body_text
                    sample.like_count = item.like_count
                    sample.published_at = item.published_at
                    sample.provider_fetch_id = result.provider_fetch_id
                    sample.captured_at = datetime.now(timezone.utc)
                    updated += 1
            self.db.commit()
            pages_fetched += 1
            if not page.has_more or not page.cursor:
                break
            cursor = page.cursor
            index = page.index
            page_area = page.page_area
        content.comments_hydrated_at = datetime.now(timezone.utc)
        self.db.commit()
        return {
            "external_content_id": str(content.id),
            "pages_fetched": pages_fetched,
            "comments_created": created,
            "comments_updated": updated,
        }

    @staticmethod
    def _payload_content_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["external_content_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="COMMENT_FETCH job is missing external_content_id.",
                retryable=False,
            ) from exc
