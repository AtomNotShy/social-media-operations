from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import WorkspaceContext, get_db, get_workspace_context, require_owner
from app.db.models import (
    AICostLedger,
    AnalysisRun,
    ContentScore,
    ExternalContent,
    SyncJob,
    TrackedProfile,
    WorkspaceInspiration,
)
from app.modules.automation.schemas import (
    AutomationCandidate,
    AutomationSettings,
    AutomationSettingsPatch,
    AutomationToday,
)
from app.modules.automation.service import (
    get_automation_settings,
    local_day_bounds,
    update_automation_settings,
    workspace_local_date,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])


@router.get("/settings", response_model=DataResponse[AutomationSettings])
def read_settings(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
) -> DataResponse:
    return DataResponse(
        data=get_automation_settings(context.workspace),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/settings", response_model=DataResponse[AutomationSettings])
def patch_settings(
    body: AutomationSettingsPatch,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DataResponse:
    settings = update_automation_settings(context.workspace, body)
    if body.scan_interval_hours is not None or body.enabled is True:
        now = datetime.now(timezone.utc)
        profiles = db.scalars(
            select(TrackedProfile).where(
                TrackedProfile.workspace_id == context.workspace.id,
                TrackedProfile.active.is_(True),
            )
        ).all()
        for profile in profiles:
            basis = profile.last_synced_at or now
            if basis.tzinfo is None:
                basis = basis.replace(tzinfo=timezone.utc)
            profile.next_scan_at = basis + timedelta(hours=settings.scan_interval_hours)
    db.commit()
    return DataResponse(
        data=settings,
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/today", response_model=DataResponse[AutomationToday])
def today(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    start, end = local_day_bounds(context.workspace)
    jobs = db.scalars(
        select(SyncJob).where(
            SyncJob.workspace_id == context.workspace.id,
            SyncJob.created_at >= start,
            SyncJob.created_at <= end,
        )
    ).all()
    scan_jobs = [job for job in jobs if job.job_type == "PROFILE_SCAN"]
    discovered = sum(int((job.result or {}).get("contents_created", 0)) for job in scan_jobs)
    scores = db.scalars(
        select(ContentScore).where(
            ContentScore.workspace_id == context.workspace.id,
            ContentScore.calculated_at >= start,
            ContentScore.calculated_at <= end,
        ).order_by(ContentScore.calculated_at.desc(), ContentScore.id.desc())
    ).all()
    latest_scores: dict = {}
    for score in scores:
        latest_scores.setdefault(score.external_content_id, score)
    observing = sum(
        1 for score in latest_scores.values()
        if bool((score.evidence or {}).get("automation_gate", {}).get("observing"))
    )
    threshold_passed = sum(
        1 for score in latest_scores.values()
        if bool((score.evidence or {}).get("automation_gate", {}).get("passed"))
    )
    runs = db.scalars(
        select(AnalysisRun).where(
            AnalysisRun.workspace_id == context.workspace.id,
            AnalysisRun.created_at >= start,
            AnalysisRun.created_at <= end,
        )
    ).all()
    latest_l1: dict = {}
    latest_l2: dict = {}
    for run in sorted(runs, key=lambda value: value.created_at, reverse=True):
        if run.analysis_level == "l1":
            latest_l1.setdefault(run.external_content_id, run)
        elif run.analysis_level == "l2":
            latest_l2.setdefault(run.external_content_id, run)
    rows = db.execute(
        select(WorkspaceInspiration, ExternalContent).join(
            ExternalContent, ExternalContent.id == WorkspaceInspiration.external_content_id
        ).where(
            WorkspaceInspiration.workspace_id == context.workspace.id,
            WorkspaceInspiration.external_content_id.in_(latest_scores.keys()),
        )
    ).all() if latest_scores else []
    candidates: list[AutomationCandidate] = []
    for inspiration, content in rows:
        score = latest_scores[content.id]
        if score.grade not in {"t1", "t2", "qualified"}:
            continue
        l1 = latest_l1.get(content.id)
        l2 = latest_l2.get(content.id)
        evidence = score.evidence or {}
        gate = evidence.get("automation_gate", {})
        l1_result = (l1.result or {}) if l1 is not None else {}
        raw_confidence = l1_result.get("confidence")
        confidence = None
        if raw_confidence is not None:
            confidence = (
                "high"
                if float(raw_confidence) >= 0.75
                else "medium" if float(raw_confidence) >= 0.5 else "low"
            )
        candidates.append(
            AutomationCandidate(
                inspiration_id=inspiration.id,
                platform=content.platform,
                title=content.title,
                grade=score.grade,
                score_mode=evidence.get("score_mode") or (
                    "hard_threshold" if gate.get("configured") else "author_relative"
                ),
                confidence=confidence,
                opportunity_score=l1_result.get("opportunity_score"),
                content_potential_score=l1_result.get("content_potential_score"),
                l1_status=l1.status if l1 is not None else None,
                l2_status=l2.status if l2 is not None else None,
                qualified_at=score.calculated_at,
            )
        )
    candidates.sort(
        key=lambda item: (
            item.opportunity_score is not None,
            item.opportunity_score or 0,
            item.qualified_at or start,
        ),
        reverse=True,
    )
    costs = db.execute(
        select(
            func.coalesce(func.sum(AICostLedger.estimated_cost_usd), 0),
            func.coalesce(func.sum(AICostLedger.actual_cost_usd), 0),
        ).where(
            AICostLedger.workspace_id == context.workspace.id,
            AICostLedger.usage_date == workspace_local_date(context.workspace),
        )
    ).one()
    data = AutomationToday(
        timezone=context.workspace.timezone,
        window_start=start,
        window_end=end,
        scanned_profiles=len(
            {
                str(job.payload.get("tracked_profile_id"))
                for job in scan_jobs
                if job.status == "succeeded"
            }
        ),
        discovered_contents=discovered,
        observing_contents=observing,
        qualified_contents=threshold_passed,
        l1_queued=sum(
            run.analysis_level == "l1" and run.status in {"queued", "running"}
            for run in runs
        ),
        l1_completed=sum(run.analysis_level == "l1" and run.status == "succeeded" for run in runs),
        l2_queued=sum(
            run.analysis_level == "l2" and run.status in {"queued", "running"}
            for run in runs
        ),
        l2_completed=sum(run.analysis_level == "l2" and run.status == "succeeded" for run in runs),
        estimated_cost_usd=costs[0],
        actual_cost_usd=costs[1],
        candidates=candidates[:50],
    )
    return DataResponse(data=data, meta=ResponseMeta(request_id=request.state.request_id))
