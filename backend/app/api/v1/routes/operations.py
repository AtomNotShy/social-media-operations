from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
)
from app.core.config import Settings
from app.db.models import (
    ACTIVE_JOB_STATUSES,
    AICostLedger,
    AnalysisRun,
    ExternalContent,
    ProviderCircuitState,
    ProviderFetch,
    ProviderUsageDaily,
    SyncJob,
    Transcript,
)
from app.jobs.service import queue_counts
from app.modules.operations.schemas import (
    AIBudgetUsageSummary,
    AIUsageSummary,
    ASRUsageSummary,
    ProviderUsageRead,
    ProviderUsageSummary,
    QueueHealthRead,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["operations"])


def _date_bounds(
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime | None, datetime | None]:
    start = (
        datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        if date_from is not None
        else None
    )
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        if date_to is not None
        else None
    )
    return start, end


@router.get(
    "/usage/provider",
    response_model=DataResponse[ProviderUsageSummary],
)
def provider_usage(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(ProviderUsageDaily).where(
        ProviderUsageDaily.workspace_id == context.workspace.id
    )
    if date_from is not None:
        query = query.where(ProviderUsageDaily.usage_date >= date_from)
    if date_to is not None:
        query = query.where(ProviderUsageDaily.usage_date <= date_to)
    rows = db.scalars(
        query.order_by(
            ProviderUsageDaily.usage_date.desc(),
            ProviderUsageDaily.provider,
            ProviderUsageDaily.endpoint_key,
        )
    ).all()
    items = [ProviderUsageRead.model_validate(row) for row in rows]
    return DataResponse(
        data=ProviderUsageSummary(
            items=items,
            request_count=sum(item.request_count for item in items),
            success_count=sum(item.success_count for item in items),
            billable_count=sum(item.billable_count for item in items),
            estimated_cost_usd=sum(
                (item.estimated_cost_usd for item in items),
                start=Decimal("0"),
            ),
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/usage/ai",
    response_model=DataResponse[AIUsageSummary],
)
def ai_usage(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    start, end = _date_bounds(date_from, date_to)
    query = select(
        func.count(AnalysisRun.id),
        func.sum(case((AnalysisRun.status == "succeeded", 1), else_=0)),
        func.sum(AnalysisRun.input_tokens),
        func.sum(AnalysisRun.output_tokens),
        func.sum(AnalysisRun.cost_usd),
    ).where(AnalysisRun.workspace_id == context.workspace.id)
    if start is not None:
        query = query.where(AnalysisRun.created_at >= start)
    if end is not None:
        query = query.where(AnalysisRun.created_at < end)
    row = db.execute(query).one()
    return DataResponse(
        data=AIUsageSummary(
            run_count=row[0] or 0,
            success_count=row[1] or 0,
            input_tokens=row[2] or 0,
            output_tokens=row[3] or 0,
            cost_usd=row[4] or Decimal("0"),
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/usage/asr",
    response_model=DataResponse[ASRUsageSummary],
)
def asr_usage(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    start, end = _date_bounds(date_from, date_to)
    query = (
        select(
            func.count(Transcript.id),
            func.sum(case((Transcript.status == "succeeded", 1), else_=0)),
            func.sum(ExternalContent.duration_ms),
            func.sum(Transcript.cost_usd),
        )
        .join(ExternalContent, ExternalContent.id == Transcript.external_content_id)
        .where(Transcript.workspace_id == context.workspace.id)
    )
    if start is not None:
        query = query.where(Transcript.created_at >= start)
    if end is not None:
        query = query.where(Transcript.created_at < end)
    row = db.execute(query).one()
    return DataResponse(
        data=ASRUsageSummary(
            transcript_count=row[0] or 0,
            success_count=row[1] or 0,
            audio_duration_ms=row[2] or 0,
            cost_usd=row[3] or Decimal("0"),
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/usage/ai-budget",
    response_model=DataResponse[AIBudgetUsageSummary],
)
def ai_budget_usage(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(
        func.count(AICostLedger.id),
        func.sum(case((AICostLedger.status == "reserved", 1), else_=0)),
        func.sum(case((AICostLedger.status == "settled", 1), else_=0)),
        func.sum(case((AICostLedger.status == "uncertain", 1), else_=0)),
        func.sum(
            case(
                (
                    AICostLedger.status == "reserved",
                    AICostLedger.estimated_cost_usd,
                ),
                else_=0,
            )
        ),
        func.sum(
            case(
                (
                    AICostLedger.status == "settled",
                    func.coalesce(
                        AICostLedger.actual_cost_usd,
                        AICostLedger.estimated_cost_usd,
                    ),
                ),
                else_=0,
            )
        ),
        func.sum(
            case(
                (
                    AICostLedger.status == "uncertain",
                    AICostLedger.estimated_cost_usd,
                ),
                else_=0,
            )
        ),
    ).where(AICostLedger.workspace_id == context.workspace.id)
    if date_from is not None:
        query = query.where(AICostLedger.usage_date >= date_from)
    if date_to is not None:
        query = query.where(AICostLedger.usage_date <= date_to)
    row = db.execute(query).one()
    reserved_cost = row[4] or Decimal("0.000000")
    settled_cost = row[5] or Decimal("0.000000")
    uncertain_cost = row[6] or Decimal("0.000000")
    return DataResponse(
        data=AIBudgetUsageSummary(
            ledger_count=row[0] or 0,
            reserved_count=row[1] or 0,
            settled_count=row[2] or 0,
            uncertain_count=row[3] or 0,
            reserved_cost_usd=reserved_cost,
            settled_cost_usd=settled_cost,
            uncertain_cost_usd=uncertain_cost,
            effective_cost_usd=reserved_cost + settled_cost + uncertain_cost,
            daily_budget_usd=context.workspace.daily_ai_budget_usd,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/system/queue-health",
    response_model=DataResponse[QueueHealthRead],
)
def queue_health(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.job_lock_timeout_seconds)
    counts = queue_counts(db, workspace_id=context.workspace.id)
    oldest_active = db.scalar(
        select(func.min(SyncJob.created_at)).where(
            SyncJob.workspace_id == context.workspace.id,
            SyncJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    )
    stale_running = db.scalar(
        select(func.count(SyncJob.id)).where(
            SyncJob.workspace_id == context.workspace.id,
            SyncJob.status == "running",
            or_(
                SyncJob.heartbeat_at < cutoff,
                SyncJob.heartbeat_at.is_(None) & (SyncJob.locked_at < cutoff),
            ),
        )
    )
    return DataResponse(
        data=QueueHealthRead(
            counts=counts,
            active_count=sum(counts.get(status, 0) for status in ACTIVE_JOB_STATUSES),
            oldest_active_created_at=oldest_active,
            stale_running_count=stale_running or 0,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/system/provider-health")
def provider_health(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = db.execute(
        select(
            ProviderFetch.endpoint_key,
            func.count(ProviderFetch.id),
            func.sum(case((ProviderFetch.error_code.is_(None), 1), else_=0)),
            func.sum(case((ProviderFetch.error_code.is_not(None), 1), else_=0)),
            func.avg(ProviderFetch.latency_ms),
            func.sum(ProviderFetch.estimated_cost_usd),
            func.max(ProviderFetch.fetched_at),
        )
        .where(
            ProviderFetch.workspace_id == context.workspace.id,
            ProviderFetch.fetched_at >= since,
        )
        .group_by(ProviderFetch.endpoint_key)
        .order_by(ProviderFetch.endpoint_key)
    ).all()
    circuits = {
        item.endpoint_key: item
        for item in db.scalars(
            select(ProviderCircuitState).where(
                ProviderCircuitState.workspace_id == context.workspace.id
            )
        ).all()
    }
    endpoints = []
    seen = set()
    for (
        endpoint_key,
        request_count,
        success_count,
        failure_count,
        average_latency,
        estimated_cost,
        last_request_at,
    ) in rows:
        circuit = circuits.get(endpoint_key)
        seen.add(endpoint_key)
        endpoints.append(
            {
                "endpoint_key": endpoint_key,
                "request_count_24h": request_count,
                "success_count_24h": success_count or 0,
                "failure_count_24h": failure_count or 0,
                "average_latency_ms_24h": (
                    round(float(average_latency), 2) if average_latency is not None else None
                ),
                "estimated_cost_usd_24h": str(estimated_cost or Decimal("0")),
                "last_request_at": last_request_at,
                "circuit": {
                    "state": circuit.state if circuit is not None else "closed",
                    "consecutive_failures": (
                        circuit.consecutive_failures if circuit is not None else 0
                    ),
                    "retry_after": circuit.retry_after if circuit is not None else None,
                    "last_error_code": (circuit.last_error_code if circuit is not None else None),
                },
            }
        )
    for endpoint_key, circuit in circuits.items():
        if endpoint_key in seen:
            continue
        endpoints.append(
            {
                "endpoint_key": endpoint_key,
                "request_count_24h": 0,
                "success_count_24h": 0,
                "failure_count_24h": 0,
                "average_latency_ms_24h": None,
                "estimated_cost_usd_24h": "0",
                "last_request_at": None,
                "circuit": {
                    "state": circuit.state,
                    "consecutive_failures": circuit.consecutive_failures,
                    "retry_after": circuit.retry_after,
                    "last_error_code": circuit.last_error_code,
                },
            }
        )
    return DataResponse(
        data={"provider": "tikhub", "endpoints": endpoints},
        meta=ResponseMeta(request_id=request.state.request_id),
    )
