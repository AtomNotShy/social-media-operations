import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, ContentMetricSnapshot, ExternalContent, Workspace
from app.modules.automation.schemas import AutomationSettings, AutomationSettingsPatch


def get_automation_settings(workspace: Workspace) -> AutomationSettings:
    raw = (workspace.settings or {}).get("automation", {})
    return AutomationSettings.model_validate(raw if isinstance(raw, dict) else {})


def update_automation_settings(
    workspace: Workspace,
    patch: AutomationSettingsPatch,
) -> AutomationSettings:
    current = get_automation_settings(workspace).model_dump(mode="json")
    changes = patch.model_dump(exclude_unset=True, exclude_none=True, mode="json")
    metric_changes = changes.pop("metric_thresholds", None)
    current.update(changes)
    if metric_changes is not None:
        current["metric_thresholds"].update(metric_changes)
    validated = AutomationSettings.model_validate(current)
    all_settings = dict(workspace.settings or {})
    all_settings["automation"] = validated.model_dump(mode="json")
    workspace.settings = all_settings
    return validated


def local_day_bounds(
    workspace: Workspace,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    try:
        zone = ZoneInfo(workspace.timezone)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    current = now or datetime.now(timezone.utc)
    local_date = current.astimezone(zone).date()
    start = datetime.combine(local_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(local_date, time.max, tzinfo=zone).astimezone(timezone.utc)
    return start, end


def workspace_local_date(workspace: Workspace, now: datetime | None = None):
    try:
        zone = ZoneInfo(workspace.timezone)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    return (now or datetime.now(timezone.utc)).astimezone(zone).date()


def daily_analysis_count(
    db: Session,
    *,
    workspace: Workspace,
    level: str,
    now: datetime | None = None,
) -> int:
    start, end = local_day_bounds(workspace, now)
    return int(
        db.scalar(
            select(func.count(AnalysisRun.id)).where(
                AnalysisRun.workspace_id == workspace.id,
                AnalysisRun.analysis_level == level,
                AnalysisRun.created_at >= start,
                AnalysisRun.created_at <= end,
                AnalysisRun.status.in_(("queued", "running", "succeeded")),
            )
        )
        or 0
    )


def within_daily_analysis_limit(
    db: Session,
    *,
    workspace: Workspace,
    level: str,
    policy: AutomationSettings | None = None,
) -> bool:
    locked_workspace = db.scalar(
        select(Workspace).where(Workspace.id == workspace.id).with_for_update()
    )
    workspace = locked_workspace or workspace
    automation = policy or get_automation_settings(workspace)
    limit = automation.daily_l1_limit if level == "l1" else automation.daily_l2_limit
    return limit > 0 and daily_analysis_count(db, workspace=workspace, level=level) < limit


@dataclass(frozen=True, slots=True)
class HardGateDecision:
    passed: bool
    observing: bool
    configured: bool
    evidence: dict


def latest_metric_snapshot(
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
        .order_by(ContentMetricSnapshot.captured_at.desc(), ContentMetricSnapshot.id.desc())
        .limit(1)
    )


def evaluate_hard_gate(
    db: Session,
    *,
    workspace: Workspace,
    content: ExternalContent,
    policy: AutomationSettings | None = None,
    now: datetime | None = None,
) -> HardGateDecision:
    automation = policy or get_automation_settings(workspace)
    current = now or datetime.now(timezone.utc)
    published = content.published_at or content.first_seen_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_minutes = max(0, (current - published).total_seconds() / 60)
    first_seen = content.first_seen_at
    if first_seen.tzinfo is None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)
    observation_age_minutes = max(0, (current - first_seen).total_seconds() / 60)
    snapshot = latest_metric_snapshot(
        db, workspace_id=workspace.id, content_id=content.id
    )
    actual = {
        name: (getattr(snapshot, name) if snapshot is not None else None)
        for name in ("views", "likes", "comments", "favorites", "shares")
    }
    thresholds = automation.metric_thresholds.model_dump()
    enabled = {name: value for name, value in thresholds.items() if value > 0}
    matches = {
        name: actual[name] is not None and int(actual[name]) >= threshold
        for name, threshold in enabled.items()
    }
    metrics_passed = (
        (any(matches.values()) if automation.threshold_match == "any" else all(matches.values()))
        if enabled
        else False
    )
    ratios = [
        min(max(float(actual[name] or 0) / threshold, 0), 1)
        for name, threshold in enabled.items()
    ]
    gate_score = (
        round(
            100
            * (
                max(ratios)
                if automation.threshold_match == "any"
                else sum(ratios) / len(ratios)
            ),
            1,
        )
        if ratios
        else 0.0
    )
    age_passed = age_minutes >= automation.minimum_age_minutes
    within_observation = observation_age_minutes <= automation.observation_hours * 60
    passed = bool(age_passed and metrics_passed and within_observation)
    reasons: list[str] = []
    if not age_passed:
        reasons.append("minimum_age_not_reached")
    if snapshot is None:
        reasons.append("candidate_metrics_missing")
    if not enabled:
        reasons.append("thresholds_not_configured")
    elif not metrics_passed:
        reasons.append("metric_threshold_not_reached")
    if not passed and not within_observation:
        reasons.append("observation_window_expired")
    return HardGateDecision(
        passed=passed,
        observing=not passed and within_observation,
        configured=bool(enabled),
        evidence={
            "passed": passed,
            "observing": not passed and within_observation,
            "configured": bool(enabled),
            "threshold_match": automation.threshold_match,
            "minimum_age_minutes": automation.minimum_age_minutes,
            "observation_hours": automation.observation_hours,
            "age_minutes": round(age_minutes, 2),
            "observation_age_minutes": round(observation_age_minutes, 2),
            "metric_snapshot_id": str(snapshot.id) if snapshot is not None else None,
            "actual": actual,
            "thresholds": thresholds,
            "matches": matches,
            "gate_score": gate_score,
            "reasons": reasons,
            "evaluated_at": current.isoformat(),
        },
    )
