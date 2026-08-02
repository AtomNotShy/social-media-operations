import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import OwnedChannel, SyncJob, Workspace
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.platforms import get_platform_binding
from app.providers.social.tikhub.registry import get_endpoint


class OwnedChannelScanHandler:
    """Fetch basic profile info (nickname, avatar, bio, handle) for a self-owned channel."""

    def __init__(
        self,
        db: Session,
        gateway: TikHubGateway,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.settings = settings

    async def handle(self, job: SyncJob) -> dict:
        channel_id = self._payload_channel_id(job)
        channel = self.db.scalar(
            select(OwnedChannel).where(
                OwnedChannel.id == channel_id,
                OwnedChannel.workspace_id == job.workspace_id,
            )
        )
        workspace = self.db.get(Workspace, job.workspace_id)
        if channel is None or workspace is None:
            raise TikHubError(
                code="NOT_FOUND",
                message="Owned channel or workspace no longer exists.",
                retryable=False,
            )
        if not channel.active:
            channel.sync_status = "paused"
            self.db.commit()
            return {
                "owned_channel_id": str(channel.id),
                "skipped": True,
                "skip_reason": "channel_inactive",
            }
        if not channel.external_id:
            return self._mark_unscannable(
                channel,
                "缺少平台账号 ID，无法自动扫描。请在账号编辑中补充平台账号 ID 后重新扫描。",
            )
        try:
            binding = get_platform_binding(channel.platform)
        except ValueError:
            return self._mark_unscannable(
                channel,
                f"{channel.platform} 平台暂不支持自动扫描。",
            )

        channel.sync_status = "syncing"
        channel.sync_error = None
        self.db.commit()
        try:
            result = await self.gateway.fetch(
                workspace=workspace,
                endpoint=get_endpoint(binding.profile_endpoint),
                params=binding.profile_params(channel.external_id),
                sync_job_id=job.id,
                force_refresh=True,
            )
            self.db.commit()
            normalized = binding.adapter.parse_profile(
                result.payload,
                external_id=channel.external_id,
            )
            channel.display_name = normalized.display_name
            channel.handle = normalized.handle or channel.handle
            channel.bio = normalized.bio
            channel.avatar_url = normalized.avatar_url
            if normalized.external_id:
                channel.external_id = normalized.external_id
            channel.last_synced_at = datetime.now(timezone.utc)
            channel.sync_status = "synced"
            channel.sync_error = None
            self.db.commit()
            return {
                "owned_channel_id": str(channel.id),
                "display_name": channel.display_name,
                "handle": channel.handle,
                "avatar_url": channel.avatar_url,
                "bio": channel.bio,
                "skipped": False,
            }
        except Exception:
            self.db.rollback()
            current = self.db.get(OwnedChannel, channel.id)
            if current is not None:
                current.sync_status = "error"
                current.sync_error = (
                    "扫描失败，请检查平台账号 ID 是否正确，或稍后重试。"
                )
                self.db.commit()
            raise

    def _mark_unscannable(self, channel: OwnedChannel, message: str) -> dict:
        channel.sync_status = "error"
        channel.sync_error = message
        self.db.commit()
        return {
            "owned_channel_id": str(channel.id),
            "skipped": True,
            "skip_reason": "unscannable",
            "sync_error": message,
        }

    @staticmethod
    def _payload_channel_id(job: SyncJob) -> uuid.UUID:
        try:
            return uuid.UUID(str(job.payload["owned_channel_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise TikHubError(
                code="JOB_PAYLOAD_INVALID",
                message="Owned channel scan job is missing a valid owned_channel_id.",
                retryable=False,
            ) from exc
