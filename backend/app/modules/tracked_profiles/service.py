import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Subquery

from app.db.models import (
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    WorkspaceInspiration,
)
from app.modules.tracked_profiles.schemas import (
    TrackedProfileOverviewContent,
    TrackedProfileOverviewGradeDistribution,
    TrackedProfileOverviewMetricSummary,
    TrackedProfileOverviewScoreSummary,
)


def _latest_metric_subquery(workspace_id: uuid.UUID, eligible_contents: Subquery):
    ranked = (
        select(
            ContentMetricSnapshot.external_content_id.label("content_id"),
            ContentMetricSnapshot.captured_at,
            ContentMetricSnapshot.views,
            ContentMetricSnapshot.likes,
            ContentMetricSnapshot.comments,
            ContentMetricSnapshot.favorites,
            ContentMetricSnapshot.shares,
            ContentMetricSnapshot.downloads,
            func.row_number()
            .over(
                partition_by=ContentMetricSnapshot.external_content_id,
                order_by=(
                    ContentMetricSnapshot.captured_at.desc(),
                    ContentMetricSnapshot.id.desc(),
                ),
            )
            .label("row_number"),
        )
        .join(
            eligible_contents,
            eligible_contents.c.content_id == ContentMetricSnapshot.external_content_id,
        )
        .where(ContentMetricSnapshot.workspace_id == workspace_id)
        .subquery("ranked_profile_content_metrics")
    )
    return select(ranked).where(ranked.c.row_number == 1).subquery("latest_profile_metrics")


def _latest_score_subquery(workspace_id: uuid.UUID, eligible_contents: Subquery):
    ranked = (
        select(
            ContentScore.external_content_id.label("content_id"),
            ContentScore.calculated_at,
            ContentScore.grade,
            ContentScore.tier,
            ContentScore.r_value,
            ContentScore.m_value,
            func.row_number()
            .over(
                partition_by=ContentScore.external_content_id,
                order_by=(ContentScore.calculated_at.desc(), ContentScore.id.desc()),
            )
            .label("row_number"),
        )
        .join(
            eligible_contents,
            eligible_contents.c.content_id == ContentScore.external_content_id,
        )
        .where(ContentScore.workspace_id == workspace_id)
        .subquery("ranked_profile_content_scores")
    )
    return select(ranked).where(ranked.c.row_number == 1).subquery("latest_profile_scores")


def _cover_url(media_manifest: list) -> str | None:
    media = [item for item in media_manifest if isinstance(item, dict)]
    for preferred_type in ("cover", "photo", "image", "thumbnail"):
        for item in media:
            url = item.get("url")
            if item.get("type") == preferred_type and isinstance(url, str) and url:
                return url
    for item in media:
        url = item.get("url")
        if isinstance(url, str) and url:
            return url
    return None


def profile_content_overview(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    profile_id: uuid.UUID,
    window_days: int,
    limit: int,
) -> tuple[int, int, TrackedProfileOverviewGradeDistribution, list[TrackedProfileOverviewContent]]:
    """Build a profile's content-intelligence overview with a fixed query count."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    profile_contents = (
        ExternalContent.workspace_id == workspace_id,
        ExternalContent.tracked_profile_id == profile_id,
        ExternalContent.deleted_at_source.is_(None),
    )
    eligible_contents = (
        select(ExternalContent.id.label("content_id"))
        .where(*profile_contents, ExternalContent.first_seen_at >= cutoff)
        .subquery("eligible_profile_contents")
    )
    latest_metrics = _latest_metric_subquery(workspace_id, eligible_contents)
    latest_scores = _latest_score_subquery(workspace_id, eligible_contents)
    total_content_count = int(
        db.scalar(select(func.count(ExternalContent.id)).where(*profile_contents)) or 0
    )

    grade_rows = db.execute(
        select(func.lower(latest_scores.c.grade), func.count(ExternalContent.id))
        .select_from(ExternalContent)
        .outerjoin(latest_scores, latest_scores.c.content_id == ExternalContent.id)
        .where(*profile_contents, ExternalContent.first_seen_at >= cutoff)
        .group_by(func.lower(latest_scores.c.grade))
    ).all()
    distribution = {"t1": 0, "t2": 0, "t3": 0, "qualified": 0, "normal": 0}
    recent_content_count = 0
    for grade, count in grade_rows:
        count = int(count)
        recent_content_count += count
        key = grade if grade in {"t1", "t2", "t3", "qualified"} else "normal"
        distribution[key] += count

    rows = db.execute(
        select(
            ExternalContent,
            latest_metrics.c.captured_at.label("metric_captured_at"),
            latest_metrics.c.views,
            latest_metrics.c.likes,
            latest_metrics.c.comments,
            latest_metrics.c.favorites,
            latest_metrics.c.shares,
            latest_metrics.c.downloads,
            latest_scores.c.calculated_at.label("score_calculated_at"),
            latest_scores.c.grade,
            latest_scores.c.tier,
            latest_scores.c.r_value,
            latest_scores.c.m_value,
            WorkspaceInspiration.id.label("inspiration_id"),
        )
        .select_from(ExternalContent)
        .outerjoin(latest_metrics, latest_metrics.c.content_id == ExternalContent.id)
        .outerjoin(latest_scores, latest_scores.c.content_id == ExternalContent.id)
        .outerjoin(
            WorkspaceInspiration,
            (WorkspaceInspiration.external_content_id == ExternalContent.id)
            & (WorkspaceInspiration.workspace_id == workspace_id),
        )
        .where(*profile_contents, ExternalContent.first_seen_at >= cutoff)
        .order_by(
            ExternalContent.published_at.is_(None),
            ExternalContent.published_at.desc(),
            ExternalContent.first_seen_at.desc(),
            ExternalContent.id.desc(),
        )
        .limit(limit)
    ).all()

    contents = []
    for row in rows:
        content = row[0]
        latest_metric = None
        if row.metric_captured_at is not None:
            latest_metric = TrackedProfileOverviewMetricSummary(
                captured_at=row.metric_captured_at,
                views=row.views,
                likes=row.likes,
                comments=row.comments,
                favorites=row.favorites,
                shares=row.shares,
                downloads=row.downloads,
            )
        latest_score = None
        if row.score_calculated_at is not None:
            latest_score = TrackedProfileOverviewScoreSummary(
                calculated_at=row.score_calculated_at,
                grade=row.grade,
                tier=row.tier,
                r_value=row.r_value,
                m_value=row.m_value,
            )
        contents.append(
            TrackedProfileOverviewContent(
                id=content.id,
                platform=content.platform,
                external_id=content.external_id,
                canonical_url=content.canonical_url,
                content_type=content.content_type,
                title=content.title,
                cover_url=_cover_url(content.media_manifest),
                published_at=content.published_at,
                first_seen_at=content.first_seen_at,
                latest_metrics=latest_metric,
                latest_score=latest_score,
                in_inspiration_library=row.inspiration_id is not None,
                inspiration_id=row.inspiration_id,
            )
        )

    return (
        total_content_count,
        recent_content_count,
        TrackedProfileOverviewGradeDistribution(**distribution),
        contents,
    )
