import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DiscoveryResult, DiscoverySearch, SyncJob, Workspace
from app.jobs.errors import JobExecutionError
from app.modules.discovery.service import serialize_content
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.registry import get_endpoint
from app.providers.social.tikhub.xiaohongshu import XiaohongshuAppV2Adapter


class DiscoverySearchHandler:
    def __init__(
        self,
        db: Session,
        gateway: TikHubGateway,
        adapter: XiaohongshuAppV2Adapter | None = None,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.adapter = adapter or XiaohongshuAppV2Adapter()

    async def handle(self, job: SyncJob) -> dict:
        search_id = self._payload_search_id(job)
        search = self.db.scalar(
            select(DiscoverySearch).where(
                DiscoverySearch.id == search_id,
                DiscoverySearch.workspace_id == job.workspace_id,
            )
        )
        workspace = self.db.get(Workspace, job.workspace_id)
        if search is None or workspace is None:
            raise JobExecutionError(
                code="NOT_FOUND",
                message="Discovery search or workspace no longer exists.",
                retryable=False,
            )
        if search.platform != "xiaohongshu":
            raise JobExecutionError(
                code="UNSUPPORTED_PLATFORM_CAPABILITY",
                message=f"Search is not implemented for {search.platform}.",
                retryable=False,
            )
        search.status = "running"
        search.started_at = datetime.now(timezone.utc)
        search.error_code = None
        search.error_message = None
        self.db.commit()
        provider_search_id: str | None = None
        search_session_id: str | None = None
        rank = 0
        try:
            for page_number in range(1, search.max_pages + 1):
                result = await self.gateway.fetch(
                    workspace=workspace,
                    endpoint=get_endpoint("xhs.search_notes"),
                    params={
                        "keyword": search.query,
                        "page": page_number,
                        "sort_type": search.parameters.get("sort_type", "general"),
                        "note_type": search.parameters.get("note_type", "不限"),
                        "time_filter": search.parameters.get("time_filter", "不限"),
                        "search_id": provider_search_id,
                        "search_session_id": search_session_id,
                        "source": "explore_feed",
                        "ai_mode": 0,
                    },
                    sync_job_id=job.id,
                )
                self.db.commit()
                parsed = self.adapter.parse_search_results(result.payload)
                provider_search_id = parsed.search_id or provider_search_id
                search_session_id = parsed.search_session_id or search_session_id
                for item in parsed.items:
                    existing = self.db.scalar(
                        select(DiscoveryResult).where(
                            DiscoveryResult.discovery_search_id == search.id,
                            DiscoveryResult.platform == item.platform,
                            DiscoveryResult.external_id == item.external_id,
                        )
                    )
                    if existing is None:
                        rank += 1
                        self.db.add(
                            DiscoveryResult(
                                workspace_id=workspace.id,
                                discovery_search_id=search.id,
                                platform=item.platform,
                                external_id=item.external_id,
                                result_rank=rank,
                                summary=serialize_content(item),
                                provider_fetch_id=result.provider_fetch_id,
                            )
                        )
                    else:
                        existing.summary = serialize_content(item)
                        existing.provider_fetch_id = result.provider_fetch_id
                self.db.commit()
                if not parsed.has_more or not parsed.items:
                    break
        except TikHubError as exc:
            search.status = "failed"
            search.error_code = exc.code
            search.error_message = exc.message
            search.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            raise
        except Exception as exc:
            search.status = "failed"
            search.error_code = "DISCOVERY_NORMALIZATION_ERROR"
            search.error_message = "Discovery response normalization failed."
            search.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            raise JobExecutionError(
                code="DISCOVERY_NORMALIZATION_ERROR",
                message="Discovery response normalization failed.",
                retryable=False,
            ) from exc

        search.result_count = (
            self.db.query(DiscoveryResult)
            .filter(DiscoveryResult.discovery_search_id == search.id)
            .count()
        )
        search.status = "succeeded"
        search.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        return {
            "discovery_search_id": str(search.id),
            "result_count": search.result_count,
        }

    @staticmethod
    def _payload_search_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["discovery_search_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="DISCOVERY_SEARCH job is missing discovery_search_id.",
                retryable=False,
            ) from exc
