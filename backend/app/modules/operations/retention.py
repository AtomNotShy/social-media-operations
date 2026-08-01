from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    CommentSample,
    ContentMetricSnapshot,
    ContentScore,
    DiscoveryResult,
    ExternalContent,
    ProfileMetricSnapshot,
    ProviderFetch,
    Transcript,
    WorkspaceInspiration,
)


@dataclass(frozen=True, slots=True)
class RetentionResult:
    eligible_payloads: int
    redacted_payloads: int


@dataclass(frozen=True, slots=True)
class ContentRetentionResult:
    eligible_contents: int
    deleted_contents: int


def redact_expired_provider_payloads(
    db: Session,
    *,
    successful_retention_days: int,
    failed_retention_days: int,
    execute: bool,
    now: datetime | None = None,
) -> RetentionResult:
    current_time = now or datetime.now(timezone.utc)
    successful_cutoff = current_time - timedelta(days=successful_retention_days)
    failed_cutoff = current_time - timedelta(days=failed_retention_days)
    referenced = or_(
        exists(
            select(ProfileMetricSnapshot.id).where(
                ProfileMetricSnapshot.provider_fetch_id == ProviderFetch.id
            )
        ),
        exists(
            select(ExternalContent.id).where(
                ExternalContent.latest_provider_fetch_id == ProviderFetch.id
            )
        ),
        exists(
            select(ContentMetricSnapshot.id).where(
                ContentMetricSnapshot.provider_fetch_id == ProviderFetch.id
            )
        ),
        exists(select(CommentSample.id).where(CommentSample.provider_fetch_id == ProviderFetch.id)),
        exists(
            select(DiscoveryResult.id).where(DiscoveryResult.provider_fetch_id == ProviderFetch.id)
        ),
    )
    eligible = ProviderFetch.response_payload.is_not(None) & (
        (ProviderFetch.error_code.is_not(None) & (ProviderFetch.fetched_at < failed_cutoff))
        | (
            ProviderFetch.error_code.is_(None)
            & (ProviderFetch.fetched_at < successful_cutoff)
            & ~referenced
        )
    )
    ids = list(db.scalars(select(ProviderFetch.id).where(eligible)).all())
    if not execute or not ids:
        return RetentionResult(eligible_payloads=len(ids), redacted_payloads=0)
    result = db.execute(
        update(ProviderFetch).where(ProviderFetch.id.in_(ids)).values(response_payload=None)
    )
    db.commit()
    return RetentionResult(
        eligible_payloads=len(ids),
        redacted_payloads=int(result.rowcount or 0),
    )


def delete_expired_unpromoted_contents(
    db: Session,
    *,
    retention_days: int,
    execute: bool,
    batch_size: int = 100,
    now: datetime | None = None,
) -> ContentRetentionResult:
    """Remove old collected candidates that never entered the inspiration workflow.

    Manual and discovery imports are protected by their WorkspaceInspiration.
    The same condition also safely handles a deleted tracked profile, whose
    foreign key is set to NULL before this retention job runs.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=retention_days)
    unpromoted = ~exists(
        select(WorkspaceInspiration.id).where(
            WorkspaceInspiration.workspace_id == ExternalContent.workspace_id,
            WorkspaceInspiration.external_content_id == ExternalContent.id,
        )
    )
    eligible = ExternalContent.last_seen_at < cutoff
    criteria = (eligible, unpromoted)
    eligible_contents = int(
        db.scalar(select(func.count()).select_from(ExternalContent).where(*criteria)) or 0
    )
    if not execute or eligible_contents == 0:
        return ContentRetentionResult(
            eligible_contents=eligible_contents,
            deleted_contents=0,
        )

    deleted_contents = 0
    while True:
        ids = list(
            db.scalars(
                select(ExternalContent.id)
                .where(*criteria)
                .order_by(ExternalContent.last_seen_at, ExternalContent.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not ids:
            break
        # PostgreSQL enforces these as ON DELETE CASCADE/SET NULL. Explicitly
        # applying the same cleanup keeps SQLite maintenance runs safe too,
        # where foreign-key enforcement may be disabled by the host process.
        db.execute(
            update(DiscoveryResult)
            .where(DiscoveryResult.imported_external_content_id.in_(ids))
            .values(imported_external_content_id=None)
        )
        for dependent in (
            AnalysisRun,
            CommentSample,
            ContentMetricSnapshot,
            ContentScore,
            Transcript,
        ):
            db.execute(delete(dependent).where(dependent.external_content_id.in_(ids)))
        result = db.execute(
            delete(ExternalContent).where(
                ExternalContent.id.in_(ids),
                ExternalContent.last_seen_at < cutoff,
                ~exists(
                    select(WorkspaceInspiration.id).where(
                        WorkspaceInspiration.workspace_id == ExternalContent.workspace_id,
                        WorkspaceInspiration.external_content_id == ExternalContent.id,
                    )
                ),
            )
        )
        db.commit()
        deleted_contents += int(result.rowcount or 0)
    return ContentRetentionResult(
        eligible_contents=eligible_contents,
        deleted_contents=deleted_contents,
    )
