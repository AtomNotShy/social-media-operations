import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ContentMetricSnapshot,
    ExternalContent,
    WorkspaceInspiration,
)
from app.providers.social.base import NormalizedContent


def upsert_external_content(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    item: NormalizedContent,
    provider_fetch_id: uuid.UUID,
    source: str,
    tracked_profile_id: uuid.UUID | None = None,
    detail_status: str = "summary",
) -> tuple[ExternalContent, WorkspaceInspiration, bool]:
    content = db.scalar(
        select(ExternalContent).where(
            ExternalContent.workspace_id == workspace_id,
            ExternalContent.platform == item.platform,
            ExternalContent.external_id == item.external_id,
        )
    )
    now = datetime.now(timezone.utc)
    content_hash = hashlib.sha256(
        json.dumps(
            {"title": item.title, "body_text": item.body_text},
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    created = content is None
    if content is None:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform=item.platform,
            external_id=item.external_id,
            tracked_profile_id=tracked_profile_id,
            canonical_url=item.canonical_url,
            content_type=item.content_type,
            title=item.title,
            body_text=item.body_text,
            published_at=item.published_at,
            duration_ms=item.duration_ms,
            author_snapshot=item.author,
            media_manifest=item.media,
            content_hash=content_hash,
            detail_status=detail_status,
            latest_provider_fetch_id=provider_fetch_id,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(content)
        db.flush()
    else:
        content.tracked_profile_id = tracked_profile_id or content.tracked_profile_id
        content.canonical_url = item.canonical_url
        content.content_type = item.content_type
        content.title = item.title
        content.body_text = item.body_text
        content.published_at = item.published_at or content.published_at
        content.duration_ms = item.duration_ms
        content.author_snapshot = item.author
        content.media_manifest = item.media
        content.content_hash = content_hash
        content.detail_status = "detail" if detail_status == "detail" else content.detail_status
        content.latest_provider_fetch_id = provider_fetch_id
        content.last_seen_at = now

    inspiration = db.scalar(
        select(WorkspaceInspiration).where(
            WorkspaceInspiration.workspace_id == workspace_id,
            WorkspaceInspiration.external_content_id == content.id,
        )
    )
    if inspiration is None:
        inspiration = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=content.id,
            status="inbox",
            source=source,
        )
        db.add(inspiration)

    snapshot_exists = db.scalar(
        select(ContentMetricSnapshot.id).where(
            ContentMetricSnapshot.external_content_id == content.id,
            ContentMetricSnapshot.provider_fetch_id == provider_fetch_id,
        )
    )
    if snapshot_exists is None:
        db.add(
            ContentMetricSnapshot(
                workspace_id=workspace_id,
                external_content_id=content.id,
                views=item.metrics.views,
                likes=item.metrics.likes,
                comments=item.metrics.comments,
                favorites=item.metrics.favorites,
                shares=item.metrics.shares,
                downloads=item.metrics.downloads,
                metrics={},
                provider_fetch_id=provider_fetch_id,
            )
        )
    db.flush()
    return content, inspiration, created
