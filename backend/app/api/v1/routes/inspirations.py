import base64
import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import and_, or_, select
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
    ExternalContent,
    ProviderFetch,
    WorkspaceInspiration,
)
from app.jobs.service import create_job
from app.modules.inspirations.schemas import (
    ContentMetricSnapshotRead,
    ImportURLRead,
    ImportURLRequest,
    InspirationRead,
    InspirationUpdate,
)
from app.modules.inspirations.service import (
    ensure_workspace_inspiration,
    latest_score_is_qualified_clause,
)
from app.modules.tracked_profiles.schemas import ExternalContentRead
from app.providers.social.url_normalization import (
    UnsupportedSocialURL,
    normalize_content_url,
)
from app.schemas.common import DataResponse, JobAccepted, ResponseMeta

router = APIRouter(prefix="/api/v1/inspirations", tags=["inspirations"])


def _encode_cursor(inspiration: WorkspaceInspiration) -> str:
    value = f"{inspiration.created_at.isoformat()}|{inspiration.id}"
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        timestamp, inspiration_id = raw.split("|", 1)
        return datetime.fromisoformat(timestamp), uuid.UUID(inspiration_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid cursor",
            "The pagination cursor is invalid.",
        ) from exc


def _read_model(
    inspiration: WorkspaceInspiration,
    content: ExternalContent,
) -> InspirationRead:
    return InspirationRead(
        id=inspiration.id,
        status=inspiration.status,
        source=inspiration.source,
        notes=inspiration.notes,
        manual_score=inspiration.manual_score,
        created_at=inspiration.created_at,
        updated_at=inspiration.updated_at,
        content=ExternalContentRead.model_validate(content),
    )


def _get_inspiration(
    db: Session,
    workspace_id: uuid.UUID,
    inspiration_id: uuid.UUID,
) -> tuple[WorkspaceInspiration, ExternalContent]:
    row = db.execute(
        select(WorkspaceInspiration, ExternalContent)
        .join(
            ExternalContent,
            ExternalContent.id == WorkspaceInspiration.external_content_id,
        )
        .where(
            WorkspaceInspiration.workspace_id == workspace_id,
            WorkspaceInspiration.id == inspiration_id,
            ExternalContent.workspace_id == workspace_id,
        )
    ).one_or_none()
    if row is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Inspiration not found",
            "Inspiration not found.",
        )
    return row[0], row[1]


def _queue_content_refresh(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    content: ExternalContent,
) -> tuple:
    fingerprint = hashlib.sha256(content.canonical_url.encode()).hexdigest()
    return create_job(
        db,
        workspace_id=workspace_id,
        job_type="CONTENT_DETAIL_FETCH",
        dedupe_key=f"content-detail:{content.platform}:{fingerprint}",
        payload={
            "platform": content.platform,
            "canonical_url": content.canonical_url,
            "external_id": content.external_id,
            "share_text": None,
            "hydrate": True,
            "analyze": False,
        },
        priority=75,
    )


@router.post("/import-url", response_model=DataResponse[ImportURLRead])
def import_url(
    body: ImportURLRequest,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    try:
        reference = normalize_content_url(body.url)
    except UnsupportedSocialURL as exc:
        raise AppError(
            422,
            "UNSUPPORTED_PLATFORM_CAPABILITY",
            "Unsupported social URL",
            str(exc),
        ) from exc

    content_query = select(ExternalContent).where(
        ExternalContent.workspace_id == context.workspace.id,
        ExternalContent.platform == reference.platform,
    )
    if reference.external_id:
        content_query = content_query.where(ExternalContent.external_id == reference.external_id)
    else:
        content_query = content_query.where(
            ExternalContent.canonical_url == reference.canonical_url
        )
    content = db.scalar(content_query)
    inspiration = None
    if content is not None:
        inspiration = ensure_workspace_inspiration(
            db,
            workspace_id=context.workspace.id,
            external_content_id=content.id,
            source="manual_url",
        )
        now = datetime.now(timezone.utc)
        fresh_fetch_id = (
            db.scalar(
                select(ProviderFetch.id).where(
                    ProviderFetch.id == content.latest_provider_fetch_id,
                    ProviderFetch.fresh_until > now,
                    ProviderFetch.error_code.is_(None),
                )
            )
            if content.latest_provider_fetch_id
            else None
        )
        if fresh_fetch_id is not None:
            db.commit()
            response.status_code = 200
            return DataResponse(
                data=ImportURLRead(
                    inspiration_id=inspiration.id,
                    external_content_id=content.id,
                    existing=True,
                    job_id=None,
                ),
                meta=ResponseMeta(request_id=request.state.request_id),
            )

    fingerprint = hashlib.sha256(reference.canonical_url.encode()).hexdigest()
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="CONTENT_DETAIL_FETCH",
        dedupe_key=f"content-detail:{reference.platform}:{fingerprint}",
        payload={
            "platform": reference.platform,
            "canonical_url": reference.canonical_url,
            "external_id": reference.external_id,
            "share_text": reference.share_text,
            "hydrate": body.hydrate,
            "analyze": body.analyze,
        },
        priority=75,
    )
    db.commit()
    response.status_code = 202
    return DataResponse(
        data=ImportURLRead(
            inspiration_id=inspiration.id if inspiration else None,
            external_content_id=content.id if content else None,
            existing=content is not None,
            job_id=job.id,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("", response_model=DataResponse[list[InspirationRead]])
def list_inspirations(
    request: Request,
    platform: str | None = None,
    status: str | None = None,
    query: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    statement = (
        select(WorkspaceInspiration, ExternalContent)
        .join(
            ExternalContent,
            ExternalContent.id == WorkspaceInspiration.external_content_id,
        )
        .where(
            WorkspaceInspiration.workspace_id == context.workspace.id,
            ExternalContent.workspace_id == context.workspace.id,
        )
    )
    # Older profile scans created inspirations before score qualification. Keep
    # their notes/status intact but hide them until the latest evidence reaches
    # the same t1/t2 threshold used by current scan promotion.
    statement = statement.where(
        or_(
            WorkspaceInspiration.source != "tracked_profile",
            latest_score_is_qualified_clause(
                workspace_id=context.workspace.id,
                external_content_id=ExternalContent.id,
            ),
        )
    )
    if platform:
        statement = statement.where(ExternalContent.platform == platform)
    if status:
        statement = statement.where(WorkspaceInspiration.status == status)
    if query:
        query_text = query.strip()
        if query_text:
            pattern = f"%{query_text}%"
            statement = statement.where(
                or_(
                    ExternalContent.title.ilike(pattern),
                    ExternalContent.body_text.ilike(pattern),
                    WorkspaceInspiration.notes.ilike(pattern),
                    ExternalContent.platform.ilike(pattern),
                )
            )
    if cursor:
        created_at, inspiration_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                WorkspaceInspiration.created_at < created_at,
                and_(
                    WorkspaceInspiration.created_at == created_at,
                    WorkspaceInspiration.id < inspiration_id,
                ),
            )
        )
    rows = db.execute(
        statement.order_by(
            WorkspaceInspiration.created_at.desc(),
            WorkspaceInspiration.id.desc(),
        ).limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1][0]) if has_more and page else None
    return DataResponse(
        data=[_read_model(row[0], row[1]) for row in page],
        meta=ResponseMeta(
            request_id=request.state.request_id,
            next_cursor=next_cursor,
        ),
    )


@router.get("/{inspiration_id}", response_model=DataResponse[InspirationRead])
def get_inspiration(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    inspiration, content = _get_inspiration(db, context.workspace.id, inspiration_id)
    return DataResponse(
        data=_read_model(inspiration, content),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{inspiration_id}/metrics",
    response_model=DataResponse[list[ContentMetricSnapshotRead]],
)
def list_inspiration_metrics(
    inspiration_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    _, content = _get_inspiration(db, context.workspace.id, inspiration_id)
    snapshots = db.scalars(
        select(ContentMetricSnapshot)
        .where(
            ContentMetricSnapshot.workspace_id == context.workspace.id,
            ContentMetricSnapshot.external_content_id == content.id,
        )
        .order_by(
            ContentMetricSnapshot.captured_at.desc(),
            ContentMetricSnapshot.id.desc(),
        )
        .limit(limit)
    ).all()
    return DataResponse(
        data=[ContentMetricSnapshotRead.model_validate(snapshot) for snapshot in snapshots],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{inspiration_id}/hydrate-detail",
    response_model=DataResponse[JobAccepted],
    status_code=202,
)
def hydrate_inspiration_detail(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    _, content = _get_inspiration(db, context.workspace.id, inspiration_id)
    job, _ = _queue_content_refresh(
        db,
        workspace_id=context.workspace.id,
        content=content,
    )
    db.commit()
    return DataResponse(
        data=JobAccepted(job_id=job.id, status=job.status),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{inspiration_id}/refresh-metrics",
    response_model=DataResponse[JobAccepted],
    status_code=202,
)
def refresh_inspiration_metrics(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    return hydrate_inspiration_detail(inspiration_id, request, context, db)


@router.patch("/{inspiration_id}", response_model=DataResponse[InspirationRead])
def update_inspiration(
    inspiration_id: uuid.UUID,
    body: InspirationUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    inspiration, content = _get_inspiration(db, context.workspace.id, inspiration_id)
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(inspiration, name, value)
    db.commit()
    return DataResponse(
        data=_read_model(inspiration, content),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{inspiration_id}/archive", response_model=DataResponse[InspirationRead])
def archive_inspiration(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    inspiration, content = _get_inspiration(db, context.workspace.id, inspiration_id)
    inspiration.status = "archived"
    db.commit()
    return DataResponse(
        data=_read_model(inspiration, content),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{inspiration_id}/restore", response_model=DataResponse[InspirationRead])
def restore_inspiration(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    inspiration, content = _get_inspiration(db, context.workspace.id, inspiration_id)
    inspiration.status = "inbox"
    db.commit()
    return DataResponse(
        data=_read_model(inspiration, content),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
