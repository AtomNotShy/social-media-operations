from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import WorkspaceContext, get_db, get_workspace_context
from app.db.models import (
    ACTIVE_JOB_STATUSES,
    ContentProject,
    PublishPlan,
    PublishRecord,
    ReviewInsight,
    SyncJob,
)
from app.modules.dashboard.schemas import (
    PerformanceDashboardRead,
    PerformanceRecordRead,
    PerformanceTotals,
    TodayDashboardRead,
)
from app.modules.workflow.schemas import ContentProjectRead, PublishPlanRead
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return 0


def _metric_groups(metrics: dict) -> tuple[int, int, int]:
    exposure = _as_int(metrics.get("views")) + _as_int(metrics.get("impressions"))
    interactions = sum(
        _as_int(metrics.get(key)) for key in ("likes", "comments", "favorites", "shares", "saves")
    )
    conversions = sum(
        _as_int(metrics.get(key)) for key in ("conversions", "leads", "orders", "purchases")
    )
    return exposure, interactions, conversions


@router.get("/today", response_model=DataResponse[TodayDashboardRead])
def today_dashboard(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    zone = ZoneInfo(context.workspace.timezone)
    local_now = datetime.now(timezone.utc).astimezone(zone)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=zone)
    start = local_start.astimezone(timezone.utc)
    end = (local_start + timedelta(days=1)).astimezone(timezone.utc)
    projects = db.scalars(
        select(ContentProject)
        .where(
            ContentProject.workspace_id == context.workspace.id,
            ContentProject.deleted_at.is_(None),
            ContentProject.due_at >= start,
            ContentProject.due_at < end,
        )
        .order_by(ContentProject.due_at, ContentProject.id)
    ).all()
    plans = db.scalars(
        select(PublishPlan)
        .where(
            PublishPlan.workspace_id == context.workspace.id,
            PublishPlan.scheduled_at >= start,
            PublishPlan.scheduled_at < end,
        )
        .order_by(PublishPlan.scheduled_at, PublishPlan.id)
    ).all()
    active_jobs = db.scalar(
        select(func.count(SyncJob.id)).where(
            SyncJob.workspace_id == context.workspace.id,
            SyncJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    )
    reviewed_record_ids = select(ReviewInsight.publish_record_id).where(
        ReviewInsight.workspace_id == context.workspace.id
    )
    waiting_review = db.scalar(
        select(func.count(PublishRecord.id)).where(
            PublishRecord.workspace_id == context.workspace.id,
            PublishRecord.id.not_in(reviewed_record_ids),
        )
    )
    return DataResponse(
        data=TodayDashboardRead(
            timezone=context.workspace.timezone,
            window_start=start,
            window_end=end,
            projects_due=[ContentProjectRead.model_validate(item) for item in projects],
            publish_plans=[PublishPlanRead.model_validate(item) for item in plans],
            active_job_count=active_jobs or 0,
            published_waiting_review_count=waiting_review or 0,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/performance", response_model=DataResponse[PerformanceDashboardRead])
def performance_dashboard(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    to_at = datetime.now(timezone.utc)
    from_at = to_at - timedelta(days=days)
    records = db.scalars(
        select(PublishRecord)
        .where(
            PublishRecord.workspace_id == context.workspace.id,
            PublishRecord.published_at >= from_at,
            PublishRecord.published_at <= to_at,
        )
        .order_by(PublishRecord.published_at.desc(), PublishRecord.id.desc())
    ).all()
    reviews = (
        db.scalars(
            select(ReviewInsight)
            .where(
                ReviewInsight.workspace_id == context.workspace.id,
                ReviewInsight.publish_record_id.in_([item.id for item in records]),
            )
            .order_by(ReviewInsight.created_at.desc(), ReviewInsight.id.desc())
        ).all()
        if records
        else []
    )
    latest_review = {}
    for review in reviews:
        latest_review.setdefault(review.publish_record_id, review)

    total_exposure = 0
    total_interactions = 0
    total_conversions = 0
    rows = []
    for record in records:
        review = latest_review.get(record.id)
        exposure, interactions, conversions = _metric_groups(
            review.metrics if review is not None else {}
        )
        total_exposure += exposure
        total_interactions += interactions
        total_conversions += conversions
        rows.append(
            PerformanceRecordRead(
                publish_record_id=record.id,
                publish_plan_id=record.publish_plan_id,
                published_at=record.published_at,
                published_url=record.published_url,
                latest_review_window=review.review_window if review is not None else None,
                exposure=exposure,
                interactions=interactions,
                conversions=conversions,
            )
        )
    return DataResponse(
        data=PerformanceDashboardRead(
            from_at=from_at,
            to_at=to_at,
            totals=PerformanceTotals(
                published_count=len(records),
                review_count=len(reviews),
                exposure=total_exposure,
                interactions=total_interactions,
                conversions=total_conversions,
            ),
            records=rows,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
