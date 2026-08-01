import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    ContentScore,
    ExternalContent,
    ProfileMetricSnapshot,
    ScanPolicy,
    SyncJob,
    TrackedProfile,
    Workspace,
    WorkspaceInspiration,
)
from app.modules.ai_connections.service import configured_for
from app.modules.analysis.service import request_analysis
from app.modules.inspirations.service import (
    is_promotion_grade,
    promote_scored_content,
    upsert_external_content,
)
from app.modules.scoring.service import calculate_content_score
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.platforms import get_platform_binding
from app.providers.social.tikhub.registry import get_endpoint


class ProfileScanHandler:
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
        profile_id = self._payload_profile_id(job)
        profile = self.db.scalar(
            select(TrackedProfile).where(
                TrackedProfile.id == profile_id,
                TrackedProfile.workspace_id == job.workspace_id,
            )
        )
        workspace = self.db.get(Workspace, job.workspace_id)
        if profile is None or workspace is None:
            raise TikHubError(
                code="NOT_FOUND",
                message="Tracked profile or workspace no longer exists.",
                retryable=False,
            )
        try:
            binding = get_platform_binding(profile.platform)
        except ValueError as exc:
            raise TikHubError(
                code="UNSUPPORTED_PLATFORM_CAPABILITY",
                message=f"Profile scan is not implemented for {profile.platform}.",
                retryable=False,
            ) from exc
        adapter = self.adapter or binding.adapter
        if not profile.active:
            raise TikHubError(
                code="VERSION_CONFLICT",
                message="Tracked profile is paused.",
                retryable=False,
            )

        profile.sync_status = "syncing"
        self.db.commit()
        try:
            profile_result = await self._fetch_and_persist(
                workspace=workspace,
                endpoint=get_endpoint(binding.profile_endpoint),
                params=binding.profile_params(profile.external_id),
                sync_job_id=job.id,
            )
            normalized_profile = adapter.parse_profile(
                profile_result.payload,
                external_id=profile.external_id,
            )
            self._save_profile(profile, normalized_profile, profile_result.provider_fetch_id)
            self.db.commit()

            policy = self.db.get(ScanPolicy, profile.scan_policy_id)
            max_pages = max(1, min(policy.max_pages if policy else 1, 10))
            known_ids = set(
                self.db.scalars(
                    select(ExternalContent.external_id).where(
                        ExternalContent.workspace_id == workspace.id,
                        ExternalContent.tracked_profile_id == profile.id,
                    )
                ).all()
            )
            cursor: str | None = None
            created_count = 0
            updated_count = 0
            pages_fetched = 0
            observed_content_ids: set[uuid.UUID] = set()
            for _ in range(max_pages):
                page_result = await self._fetch_and_persist(
                    workspace=workspace,
                    endpoint=get_endpoint(binding.contents_endpoint),
                    params=binding.contents_params(profile.external_id, cursor, 20),
                    sync_job_id=job.id,
                )
                page = adapter.parse_profile_contents(
                    page_result.payload,
                    profile_id=profile.external_id,
                )
                page_seen_known = False
                for item in page.items:
                    existed = item.external_id in known_ids
                    page_seen_known = page_seen_known or existed
                    content, _, _ = upsert_external_content(
                        self.db,
                        workspace_id=workspace.id,
                        item=item,
                        provider_fetch_id=page_result.provider_fetch_id,
                        source="tracked_profile",
                        tracked_profile_id=profile.id,
                        create_inspiration=False,
                    )
                    observed_content_ids.add(content.id)
                    if existed:
                        updated_count += 1
                    else:
                        created_count += 1
                        known_ids.add(item.external_id)
                cursor = page.next_cursor
                profile.sync_cursor = {
                    "series": binding.series,
                    "cursor": cursor,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.db.commit()
                pages_fetched += 1
                if not cursor or page_seen_known:
                    break

            scores_created = 0
            inspirations_promoted = 0
            analyses_queued = 0
            score_errors: list[str] = []
            for content_id in observed_content_ids:
                previous_score = self.db.scalar(
                    select(ContentScore)
                    .where(
                        ContentScore.workspace_id == workspace.id,
                        ContentScore.external_content_id == content_id,
                    )
                    .order_by(ContentScore.calculated_at.desc(), ContentScore.id.desc())
                    .limit(1)
                )
                was_qualified = (
                    previous_score is not None and is_promotion_grade(previous_score.grade)
                )
                existing_inspiration = self.db.scalar(
                    select(WorkspaceInspiration).where(
                        WorkspaceInspiration.workspace_id == workspace.id,
                        WorkspaceInspiration.external_content_id == content_id,
                    )
                )
                try:
                    score = calculate_content_score(
                        self.db,
                        workspace_id=workspace.id,
                        content_id=content_id,
                    )
                    self.db.commit()
                    scores_created += 1
                    inspiration = promote_scored_content(
                        self.db,
                        workspace_id=workspace.id,
                        external_content_id=content_id,
                        grade=score.grade,
                        source="tracked_profile",
                    )
                    if inspiration is not None:
                        self.db.commit()
                    newly_qualified = inspiration is not None and not was_qualified
                    if newly_qualified:
                        inspirations_promoted += 1
                    if (
                        inspiration is not None
                        and (existing_inspiration is None or newly_qualified)
                        and self.settings is not None
                        and configured_for(
                            self.db,
                            workspace_id=workspace.id,
                            task_type="l1",
                            settings=self.settings,
                        )
                    ):
                        _, reused = request_analysis(
                            self.db,
                            workspace_id=workspace.id,
                            inspiration_id=inspiration.id,
                            level="l1",
                            force=False,
                            settings=self.settings,
                        )
                        self.db.commit()
                        if not reused:
                            analyses_queued += 1
                except AppError as exc:
                    self.db.rollback()
                    score_errors.append(exc.code)

            profile.last_synced_at = datetime.now(timezone.utc)
            profile.next_scan_at = profile.last_synced_at + timedelta(hours=24)
            profile.sync_status = "idle"
            self.db.commit()
            return {
                "tracked_profile_id": str(profile.id),
                "pages_fetched": pages_fetched,
                "contents_created": created_count,
                "contents_updated": updated_count,
                "scores_created": scores_created,
                "inspirations_promoted": inspirations_promoted,
                "analyses_queued": analyses_queued,
                "score_errors": score_errors,
            }
        except Exception:
            self.db.rollback()
            current_profile = self.db.get(TrackedProfile, profile.id)
            if current_profile is not None:
                current_profile.sync_status = "error"
                current_profile.next_scan_at = datetime.now(timezone.utc) + timedelta(hours=1)
                self.db.commit()
            raise

    async def _fetch_and_persist(self, **kwargs):
        try:
            result = await self.gateway.fetch(**kwargs)
            self.db.commit()
            return result
        except TikHubError:
            self.db.commit()
            raise

    @staticmethod
    def _payload_profile_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["tracked_profile_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise TikHubError(
                code="JOB_PAYLOAD_INVALID",
                message="PROFILE_SCAN job is missing tracked_profile_id.",
                retryable=False,
            ) from exc

    def _save_profile(self, profile, normalized, provider_fetch_id: uuid.UUID) -> None:
        profile.display_name = normalized.display_name
        profile.handle = normalized.handle
        profile.bio = normalized.bio
        profile.avatar_url = normalized.avatar_url
        profile.follower_count_latest = normalized.followers
        exists = self.db.scalar(
            select(ProfileMetricSnapshot.id).where(
                ProfileMetricSnapshot.tracked_profile_id == profile.id,
                ProfileMetricSnapshot.provider_fetch_id == provider_fetch_id,
            )
        )
        if exists is None:
            self.db.add(
                ProfileMetricSnapshot(
                    workspace_id=profile.workspace_id,
                    tracked_profile_id=profile.id,
                    followers=normalized.followers,
                    following=normalized.following,
                    total_likes=normalized.total_likes,
                    content_count=normalized.content_count,
                    metrics=normalized.extra_metrics,
                    provider_fetch_id=provider_fetch_id,
                )
            )
