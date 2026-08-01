import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    ProfileMetricSnapshot,
    ScoringPolicy,
)

SUPPORTED_METRICS = {"views", "likes", "comments", "favorites", "shares", "downloads"}


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid scoring policy",
            "Scoring weights and thresholds must be numeric.",
        ) from exc


def validate_scoring_policy(policy: ScoringPolicy) -> None:
    formula = policy.core_metric_formula
    for field in ("core_metric_weights", "reach_proxy_weights"):
        weights = formula.get(field)
        if not isinstance(weights, dict) or not weights:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Invalid scoring policy",
                f"{field} must contain at least one metric weight.",
            )
        unknown = set(weights) - SUPPORTED_METRICS
        if unknown:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Invalid scoring policy",
                f"Unsupported metrics: {', '.join(sorted(unknown))}.",
            )
        for weight in weights.values():
            if _decimal(weight) < 0:
                raise AppError(
                    422,
                    "VALIDATION_ERROR",
                    "Invalid scoring policy",
                    "Scoring weights cannot be negative.",
                )


def _metric_values(snapshot: ContentMetricSnapshot) -> dict[str, int | None]:
    return {
        "views": snapshot.views,
        "likes": snapshot.likes,
        "comments": snapshot.comments,
        "favorites": snapshot.favorites,
        "shares": snapshot.shares,
        "downloads": snapshot.downloads,
    }


def _weighted_metric(
    snapshot: ContentMetricSnapshot,
    weights: dict,
) -> Decimal:
    values = _metric_values(snapshot)
    return sum(
        (_decimal(weight) * Decimal(values[name] or 0) for name, weight in weights.items()),
        start=Decimal("0"),
    )


def _latest_metric_snapshot(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    content_id: uuid.UUID,
) -> ContentMetricSnapshot | None:
    return db.scalar(
        select(ContentMetricSnapshot)
        .where(
            ContentMetricSnapshot.workspace_id == workspace_id,
            ContentMetricSnapshot.external_content_id == content_id,
        )
        .order_by(
            ContentMetricSnapshot.captured_at.desc(),
            ContentMetricSnapshot.id.desc(),
        )
        .limit(1)
    )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _tier(followers: int, thresholds: dict) -> str:
    if followers <= int(thresholds.get("micro_max", 10000)):
        return "micro"
    if followers <= int(thresholds.get("small_max", 100000)):
        return "small"
    if followers <= int(thresholds.get("medium_max", 1000000)):
        return "medium"
    return "large"


def _grade(r_value: Decimal, m_value: Decimal, thresholds: dict) -> str:
    for grade in ("t1", "t2", "t3"):
        rule = thresholds.get(grade, {})
        if r_value >= _decimal(rule.get("minimum_r", Decimal("Infinity"))) and m_value >= _decimal(
            rule.get("minimum_m", Decimal("Infinity"))
        ):
            return grade
    low_quality = thresholds.get("low_quality", {})
    if r_value < _decimal(low_quality.get("maximum_r", 0)):
        return "low_quality"
    return "ordinary"


def _follower_evidence(
    db: Session,
    content: ExternalContent,
) -> tuple[int | None, uuid.UUID | None]:
    author_followers = content.author_snapshot.get("followers")
    if isinstance(author_followers, int) and author_followers >= 0:
        return author_followers, None
    if content.tracked_profile_id is None:
        return None, None
    snapshot = db.scalar(
        select(ProfileMetricSnapshot)
        .where(
            ProfileMetricSnapshot.workspace_id == content.workspace_id,
            ProfileMetricSnapshot.tracked_profile_id == content.tracked_profile_id,
        )
        .order_by(
            ProfileMetricSnapshot.captured_at.desc(),
            ProfileMetricSnapshot.id.desc(),
        )
        .limit(1)
    )
    return (
        (snapshot.followers, snapshot.id)
        if snapshot is not None and snapshot.followers is not None
        else (None, None)
    )


def calculate_content_score(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    content_id: uuid.UUID,
) -> ContentScore:
    content = db.scalar(
        select(ExternalContent).where(
            ExternalContent.workspace_id == workspace_id,
            ExternalContent.id == content_id,
        )
    )
    if content is None:
        raise AppError(404, "NOT_FOUND", "Content not found", "Content not found.")
    policy = db.scalar(
        select(ScoringPolicy).where(
            ScoringPolicy.workspace_id == workspace_id,
            ScoringPolicy.platform == content.platform,
            ScoringPolicy.active.is_(True),
        )
    )
    if policy is None:
        raise AppError(
            409,
            "SCORING_POLICY_MISSING",
            "Scoring policy missing",
            f"No active scoring policy exists for {content.platform}.",
        )
    validate_scoring_policy(policy)
    existing_initial = db.scalar(
        select(ContentScore.id).where(
            ContentScore.workspace_id == workspace_id,
            ContentScore.external_content_id == content.id,
            ContentScore.is_initial.is_(True),
        )
    )
    is_initial = existing_initial is None
    candidate_snapshot = _latest_metric_snapshot(
        db,
        workspace_id=workspace_id,
        content_id=content.id,
    )
    reasons: list[str] = []
    if content.published_at is None:
        reasons.append("published_at_missing")
    else:
        age_minutes = (
            datetime.now(timezone.utc) - _as_utc(content.published_at)
        ).total_seconds() / 60
        if age_minutes < policy.minimum_age_minutes:
            reasons.append("minimum_age_not_reached")
    if candidate_snapshot is None:
        reasons.append("candidate_metrics_missing")

    required_metrics = policy.core_metric_formula.get("required_metrics", [])
    if candidate_snapshot is not None:
        metric_values = _metric_values(candidate_snapshot)
        missing_required = [
            name
            for name in required_metrics
            if name not in SUPPORTED_METRICS or metric_values.get(name) is None
        ]
        if missing_required:
            reasons.append("required_metrics_missing")

    baseline_records: list[tuple[ExternalContent, ContentMetricSnapshot, Decimal]] = []
    if content.tracked_profile_id is None or content.published_at is None:
        reasons.append("baseline_profile_missing")
    else:
        prior_contents = db.scalars(
            select(ExternalContent)
            .where(
                ExternalContent.workspace_id == workspace_id,
                ExternalContent.tracked_profile_id == content.tracked_profile_id,
                ExternalContent.published_at.is_not(None),
                ExternalContent.published_at < content.published_at,
            )
            .order_by(ExternalContent.published_at.desc(), ExternalContent.id.desc())
            .limit(20)
        ).all()
        for prior in prior_contents:
            snapshot = _latest_metric_snapshot(
                db,
                workspace_id=workspace_id,
                content_id=prior.id,
            )
            if snapshot is not None:
                baseline_records.append(
                    (
                        prior,
                        snapshot,
                        _weighted_metric(
                            snapshot,
                            policy.core_metric_formula["core_metric_weights"],
                        ),
                    )
                )
    if len(baseline_records) < policy.minimum_baseline_count:
        reasons.append("insufficient_baseline")

    followers, follower_snapshot_id = _follower_evidence(db, content)
    if followers is None:
        reasons.append("follower_snapshot_missing")

    core_metric = (
        _weighted_metric(
            candidate_snapshot,
            policy.core_metric_formula["core_metric_weights"],
        )
        if candidate_snapshot is not None
        else None
    )
    baseline_value = (
        Decimal(str(median([record[2] for record in baseline_records])))
        if baseline_records
        else None
    )
    reach_proxy = (
        _weighted_metric(
            candidate_snapshot,
            policy.core_metric_formula["reach_proxy_weights"],
        )
        if candidate_snapshot is not None
        else None
    )
    if reasons:
        r_value = None
        m_value = None
        tier = _tier(followers, policy.tier_thresholds) if followers is not None else None
        grade = "insufficient"
    else:
        r_value = core_metric / max(baseline_value, Decimal("1"))
        m_value = reach_proxy / max(Decimal(followers), Decimal("1"))
        tier = _tier(followers, policy.tier_thresholds)
        grade = _grade(r_value, m_value, policy.grade_thresholds)

    evidence = {
        "policy_version": policy.version,
        "candidate_metric_snapshot_id": (
            str(candidate_snapshot.id) if candidate_snapshot is not None else None
        ),
        "candidate_metrics": (
            _metric_values(candidate_snapshot) if candidate_snapshot is not None else None
        ),
        "follower_snapshot_id": (
            str(follower_snapshot_id) if follower_snapshot_id is not None else None
        ),
        "followers": followers,
        "baseline_content_ids": [str(record[0].id) for record in baseline_records],
        "baseline_metric_snapshot_ids": [str(record[1].id) for record in baseline_records],
        "baseline_values": [str(record[2]) for record in baseline_records],
        "baseline_value": str(baseline_value) if baseline_value is not None else None,
        "core_metric": str(core_metric) if core_metric is not None else None,
        "reach_proxy": str(reach_proxy) if reach_proxy is not None else None,
        "reasons": sorted(set(reasons)),
    }
    score = ContentScore(
        workspace_id=workspace_id,
        external_content_id=content.id,
        scoring_policy_id=policy.id,
        r_value=r_value,
        m_value=m_value,
        tier=tier,
        grade=grade,
        core_metric=core_metric,
        baseline_value=baseline_value,
        is_initial=is_initial,
        evidence=evidence,
        calculated_at=datetime.now(timezone.utc),
    )
    db.add(score)
    db.flush()
    return score
