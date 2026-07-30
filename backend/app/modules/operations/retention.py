from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    CommentSample,
    ContentMetricSnapshot,
    DiscoveryResult,
    ExternalContent,
    ProfileMetricSnapshot,
    ProviderFetch,
)


@dataclass(frozen=True, slots=True)
class RetentionResult:
    eligible_payloads: int
    redacted_payloads: int


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
