import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    WorkspaceInspiration,
)
from app.providers.social.base import NormalizedContent

EXPLICIT_IMPORT_SOURCES = frozenset({"manual_url", "discovery_search"})


def ensure_workspace_inspiration(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    external_content_id: uuid.UUID,
    source: str,
) -> WorkspaceInspiration:
    """Return the one workspace inspiration for content, creating it if needed."""
    inspiration = db.scalar(
        select(WorkspaceInspiration).where(
            WorkspaceInspiration.workspace_id == workspace_id,
            WorkspaceInspiration.external_content_id == external_content_id,
        )
    )
    if inspiration is not None:
        if inspiration.source == "tracked_profile" and source in EXPLICIT_IMPORT_SOURCES:
            inspiration.source = source
        return inspiration

    inspiration = WorkspaceInspiration(
        workspace_id=workspace_id,
        external_content_id=external_content_id,
        status="inbox",
        source=source,
    )
    try:
        with db.begin_nested():
            db.add(inspiration)
            db.flush()
    except IntegrityError:
        inspiration = db.scalar(
            select(WorkspaceInspiration).where(
                WorkspaceInspiration.workspace_id == workspace_id,
                WorkspaceInspiration.external_content_id == external_content_id,
            )
        )
        if inspiration is None:
            raise
    return inspiration


PROMOTION_GRADES = frozenset({"t1", "t2", "qualified"})


def is_promotion_grade(grade: str) -> bool:
    return grade in PROMOTION_GRADES


def latest_score_is_qualified_clause(
    *,
    workspace_id: uuid.UUID,
    external_content_id,
):
    latest_score_id = (
        select(ContentScore.id)
        .where(
            ContentScore.workspace_id == workspace_id,
            ContentScore.external_content_id == external_content_id,
        )
        .order_by(ContentScore.calculated_at.desc(), ContentScore.id.desc())
        .limit(1)
        .correlate(ExternalContent)
        .scalar_subquery()
    )
    return (
        select(ContentScore.grade)
        .where(ContentScore.id == latest_score_id)
        .scalar_subquery()
        .in_(PROMOTION_GRADES)
    )


def promote_scored_content(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    external_content_id: uuid.UUID,
    grade: str,
    source: str,
) -> WorkspaceInspiration | None:
    """Promote only score-qualified collected content into the inspiration workflow."""
    if not is_promotion_grade(grade):
        return None
    return ensure_workspace_inspiration(
        db,
        workspace_id=workspace_id,
        external_content_id=external_content_id,
        source=source,
    )


def upsert_external_content(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    item: NormalizedContent,
    provider_fetch_id: uuid.UUID,
    source: str,
    tracked_profile_id: uuid.UUID | None = None,
    detail_status: str = "summary",
    create_inspiration: bool = True,
) -> tuple[ExternalContent, WorkspaceInspiration | None, bool]:
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
            original_content=item.original_content,
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
        if item.original_content is not None:
            content.original_content = item.original_content
        content.content_hash = content_hash
        content.detail_status = "detail" if detail_status == "detail" else content.detail_status
        content.latest_provider_fetch_id = provider_fetch_id
        content.last_seen_at = now

    inspiration = (
        ensure_workspace_inspiration(
            db,
            workspace_id=workspace_id,
            external_content_id=content.id,
            source=source,
        )
        if create_inspiration
        else None
    )

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
