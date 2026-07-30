import hashlib
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import (
    ContentMetricSnapshot,
    DiscoveryResult,
    DiscoverySearch,
    ExternalContent,
    TrackedProfile,
    WorkspaceInspiration,
)
from app.jobs.service import create_job
from app.modules.discovery.schemas import (
    DiscoveryImportRead,
    DiscoveryImportRequest,
    DiscoveryResultRead,
    DiscoverySearchAccepted,
    DiscoverySearchEstimateRead,
    DiscoverySearchRead,
    DiscoverySearchRequest,
    TrendingItemRead,
    TrendingRefreshRead,
)
from app.modules.discovery.service import deserialize_content
from app.modules.inspirations.service import upsert_external_content
from app.providers.social.tikhub.registry import get_endpoint
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/discover", tags=["discovery"])


def _trend_score(snapshot: ContentMetricSnapshot) -> int:
    return sum(
        (value or 0) * weight
        for value, weight in (
            (snapshot.views, 1),
            (snapshot.likes, 3),
            (snapshot.comments, 5),
            (snapshot.favorites, 4),
            (snapshot.shares, 6),
        )
    )


@router.get(
    "/search-estimate",
    response_model=DataResponse[DiscoverySearchEstimateRead],
)
def estimate_search(
    request: Request,
    max_pages: int = Query(default=1, ge=1, le=5),
    context: WorkspaceContext = Depends(get_workspace_context),
) -> DataResponse:
    del context
    return DataResponse(
        data=DiscoverySearchEstimateRead(
            provider_calls=max_pages,
            estimated_provider_cost_usd=(
                get_endpoint("xhs.search_notes").estimated_cost_usd * max_pages
            ),
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


def _read_search(search: DiscoverySearch, results: list[DiscoveryResult]) -> DiscoverySearchRead:
    return DiscoverySearchRead(
        id=search.id,
        sync_job_id=search.sync_job_id,
        platform=search.platform,
        query=search.query,
        max_pages=search.max_pages,
        hydrate_top=search.hydrate_top,
        parameters=search.parameters,
        status=search.status,
        result_count=search.result_count,
        error_code=search.error_code,
        created_at=search.created_at,
        finished_at=search.finished_at,
        results=[DiscoveryResultRead.model_validate(item) for item in results],
    )


@router.post(
    "/search",
    response_model=DataResponse[DiscoverySearchAccepted],
    status_code=202,
)
def create_search(
    body: DiscoverySearchRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    search = DiscoverySearch(
        workspace_id=context.workspace.id,
        platform=body.platform,
        query=body.query.strip(),
        max_pages=body.max_pages,
        hydrate_top=body.hydrate_top,
        parameters={
            "sort_type": body.sort_type,
            "note_type": body.note_type,
            "time_filter": body.time_filter,
        },
    )
    db.add(search)
    db.flush()
    fingerprint = hashlib.sha256(
        (
            f"{body.platform}|{body.query.strip()}|{body.max_pages}|"
            f"{body.sort_type}|{body.note_type}|{body.time_filter}"
        ).encode()
    ).hexdigest()
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="DISCOVERY_SEARCH",
        dedupe_key=f"discovery-search:{fingerprint}",
        payload={"discovery_search_id": str(search.id)},
        priority=45,
    )
    if job.payload.get("discovery_search_id") != str(search.id):
        db.rollback()
        existing = db.scalar(select(DiscoverySearch).where(DiscoverySearch.sync_job_id == job.id))
        if existing is None:
            raise AppError(
                409,
                "VERSION_CONFLICT",
                "Search request conflict",
                "An equivalent search is already being created.",
            )
        search = existing
    else:
        search.sync_job_id = job.id
        db.commit()
    return DataResponse(
        data=DiscoverySearchAccepted(
            search_id=search.id,
            job_id=job.id,
            status=job.status,
            estimated_provider_cost_usd=(
                get_endpoint("xhs.search_notes").estimated_cost_usd * search.max_pages
            ),
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/search-jobs/{job_id}",
    response_model=DataResponse[DiscoverySearchRead],
)
def get_search(
    job_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    search = db.scalar(
        select(DiscoverySearch).where(
            DiscoverySearch.workspace_id == context.workspace.id,
            DiscoverySearch.sync_job_id == job_id,
        )
    )
    if search is None:
        raise AppError(404, "NOT_FOUND", "Search not found", "Search job not found.")
    results = db.scalars(
        select(DiscoveryResult)
        .where(
            DiscoveryResult.workspace_id == context.workspace.id,
            DiscoveryResult.discovery_search_id == search.id,
        )
        .order_by(DiscoveryResult.result_rank)
    ).all()
    return DataResponse(
        data=_read_search(search, results),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/search-jobs/{job_id}/import",
    response_model=DataResponse[DiscoveryImportRead],
)
def import_search_results(
    job_id: uuid.UUID,
    body: DiscoveryImportRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    search = db.scalar(
        select(DiscoverySearch).where(
            DiscoverySearch.workspace_id == context.workspace.id,
            DiscoverySearch.sync_job_id == job_id,
        )
    )
    if search is None:
        raise AppError(404, "NOT_FOUND", "Search not found", "Search job not found.")
    if search.status != "succeeded":
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Search is not complete",
            "Results can only be imported after the search succeeds.",
        )
    unique_ids = set(body.result_ids)
    results = db.scalars(
        select(DiscoveryResult).where(
            DiscoveryResult.workspace_id == context.workspace.id,
            DiscoveryResult.discovery_search_id == search.id,
            DiscoveryResult.id.in_(unique_ids),
        )
    ).all()
    if len(results) != len(unique_ids):
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid discovery result",
            "One or more selected results do not belong to this search.",
        )
    inspiration_ids = []
    hydration_job_ids = []
    for result in results:
        item = deserialize_content(result.summary)
        content, inspiration, _ = upsert_external_content(
            db,
            workspace_id=context.workspace.id,
            item=item,
            provider_fetch_id=result.provider_fetch_id,
            source="discovery_search",
        )
        result.imported_external_content_id = content.id
        inspiration_ids.append(inspiration.id)
        if body.hydrate:
            fingerprint = hashlib.sha256(item.canonical_url.encode()).hexdigest()
            job, _ = create_job(
                db,
                workspace_id=context.workspace.id,
                job_type="CONTENT_DETAIL_FETCH",
                dedupe_key=f"content-detail:{item.platform}:{fingerprint}",
                payload={
                    "platform": item.platform,
                    "canonical_url": item.canonical_url,
                    "external_id": item.external_id,
                    "share_text": None,
                    "hydrate": True,
                    "analyze": False,
                },
                priority=75,
            )
            hydration_job_ids.append(job.id)
    db.commit()
    return DataResponse(
        data=DiscoveryImportRead(
            inspiration_ids=inspiration_ids,
            hydration_job_ids=hydration_job_ids,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/trending", response_model=DataResponse[list[TrendingItemRead]])
def list_trending(
    request: Request,
    platform: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    latest = (
        select(
            ContentMetricSnapshot.external_content_id.label("content_id"),
            func.max(ContentMetricSnapshot.captured_at).label("captured_at"),
        )
        .where(ContentMetricSnapshot.workspace_id == context.workspace.id)
        .group_by(ContentMetricSnapshot.external_content_id)
        .subquery()
    )
    statement = (
        select(
            WorkspaceInspiration,
            ExternalContent,
            ContentMetricSnapshot,
        )
        .join(
            ExternalContent,
            ExternalContent.id == WorkspaceInspiration.external_content_id,
        )
        .join(latest, latest.c.content_id == ExternalContent.id)
        .join(
            ContentMetricSnapshot,
            (ContentMetricSnapshot.external_content_id == latest.c.content_id)
            & (ContentMetricSnapshot.captured_at == latest.c.captured_at),
        )
        .where(
            WorkspaceInspiration.workspace_id == context.workspace.id,
            ExternalContent.workspace_id == context.workspace.id,
            ContentMetricSnapshot.workspace_id == context.workspace.id,
        )
    )
    if platform:
        statement = statement.where(ExternalContent.platform == platform)
    rows = db.execute(statement).all()
    ranked = sorted(rows, key=lambda row: (_trend_score(row[2]), str(row[1].id)), reverse=True)
    data = []
    for inspiration, content, snapshot in ranked[:limit]:
        data.append(
            TrendingItemRead(
                inspiration_id=inspiration.id,
                external_content_id=content.id,
                platform=content.platform,
                external_id=content.external_id,
                canonical_url=content.canonical_url,
                title=content.title,
                published_at=content.published_at,
                trend_score=_trend_score(snapshot),
                source="workspace_metric_snapshot",
                evidence_snapshot_id=snapshot.id,
                evidence_captured_at=snapshot.captured_at,
                metrics={
                    "views": snapshot.views,
                    "likes": snapshot.likes,
                    "comments": snapshot.comments,
                    "favorites": snapshot.favorites,
                    "shares": snapshot.shares,
                    "downloads": snapshot.downloads,
                },
            )
        )
    return DataResponse(
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/trending/refresh",
    response_model=DataResponse[TrendingRefreshRead],
    status_code=202,
)
def refresh_trending(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    profiles = db.scalars(
        select(TrackedProfile)
        .where(
            TrackedProfile.workspace_id == context.workspace.id,
            TrackedProfile.active.is_(True),
        )
        .order_by(TrackedProfile.priority.desc(), TrackedProfile.id)
        .limit(limit)
    ).all()
    queued_job_ids = []
    for profile in profiles:
        job, _ = create_job(
            db,
            workspace_id=context.workspace.id,
            job_type="PROFILE_SCAN",
            dedupe_key=f"profile-sync:{profile.id}",
            payload={
                "tracked_profile_id": str(profile.id),
                "source": "trending_refresh",
            },
            priority=profile.priority,
        )
        queued_job_ids.append(job.id)
    inactive_count = db.scalar(
        select(func.count(TrackedProfile.id)).where(
            TrackedProfile.workspace_id == context.workspace.id,
            TrackedProfile.active.is_(False),
        )
    )
    db.commit()
    return DataResponse(
        data=TrendingRefreshRead(
            queued_job_ids=queued_job_ids,
            skipped_inactive_count=inactive_count or 0,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
