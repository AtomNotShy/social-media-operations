import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import (
    ExternalContent,
    ProfileMetricSnapshot,
    ScanPolicy,
    SyncJob,
    TrackedProfile,
)
from app.jobs.schemas import JobRead
from app.jobs.service import create_job
from app.modules.tracked_profiles.schemas import (
    ExternalContentRead,
    ProfileMetricSnapshotRead,
    TrackedProfileCreate,
    TrackedProfileImportRequest,
    TrackedProfileRead,
    TrackedProfileUpdate,
)
from app.providers.social.tikhub.platforms import get_platform_binding
from app.schemas.common import DataResponse, JobAccepted, ResponseMeta

router = APIRouter(prefix="/api/v1/tracked-profiles", tags=["tracked-profiles"])


def _encode_cursor(item: TrackedProfile) -> str:
    value = f"{item.created_at.isoformat()}|{item.id}"
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        timestamp, profile_id = raw.split("|", 1)
        return datetime.fromisoformat(timestamp), uuid.UUID(profile_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid cursor",
            "The pagination cursor is invalid.",
        ) from exc


def _get_profile(db: Session, workspace_id: uuid.UUID, profile_id: uuid.UUID) -> TrackedProfile:
    profile = db.scalar(
        select(TrackedProfile).where(
            TrackedProfile.workspace_id == workspace_id,
            TrackedProfile.id == profile_id,
        )
    )
    if profile is None:
        raise AppError(404, "NOT_FOUND", "Profile not found", "Tracked profile not found.")
    return profile


def _scan_policy(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    scan_policy_id: uuid.UUID | None,
) -> ScanPolicy:
    statement = select(ScanPolicy).where(ScanPolicy.workspace_id == workspace_id)
    if scan_policy_id is None:
        statement = statement.where(ScanPolicy.active.is_(True))
    else:
        statement = statement.where(ScanPolicy.id == scan_policy_id)
    policy = db.scalar(statement.order_by(ScanPolicy.created_at).limit(1))
    if policy is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Scan policy not found",
            "A scan policy from the current workspace is required.",
        )
    return policy


def _validate_platform(platform: str) -> None:
    try:
        get_platform_binding(platform)
    except ValueError as exc:
        raise AppError(
            422,
            "UNSUPPORTED_PLATFORM_CAPABILITY",
            "Unsupported tracked profile platform",
            f"Tracked profile scanning is not implemented for {platform}.",
        ) from exc


def _new_profile(
    *,
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: TrackedProfileCreate,
) -> TrackedProfile:
    return TrackedProfile(
        workspace_id=workspace_id,
        platform=body.platform,
        external_id=body.external_id,
        profile_url=body.profile_url,
        display_name=body.display_name,
        handle=body.handle,
        priority=body.priority,
        scan_policy_id=policy_id,
        next_scan_at=datetime.now(timezone.utc),
    )


@router.get("", response_model=DataResponse[list[TrackedProfileRead]])
def list_profiles(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    active: bool | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(TrackedProfile).where(TrackedProfile.workspace_id == context.workspace.id)
    if active is not None:
        query = query.where(TrackedProfile.active == active)
    if cursor:
        created_at, profile_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                TrackedProfile.created_at > created_at,
                and_(
                    TrackedProfile.created_at == created_at,
                    TrackedProfile.id > profile_id,
                ),
            )
        )
    items = db.scalars(
        query.order_by(TrackedProfile.created_at, TrackedProfile.id).limit(limit + 1)
    ).all()
    has_more = len(items) > limit
    page = items[:limit]
    next_cursor = _encode_cursor(page[-1]) if has_more and page else None
    return DataResponse(
        data=[TrackedProfileRead.model_validate(item) for item in page],
        meta=ResponseMeta(
            request_id=request.state.request_id,
            next_cursor=next_cursor,
        ),
    )


@router.post(
    "",
    response_model=DataResponse[TrackedProfileRead],
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    body: TrackedProfileCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    _validate_platform(body.platform)
    policy = _scan_policy(
        db,
        workspace_id=context.workspace.id,
        scan_policy_id=body.scan_policy_id,
    )
    profile = _new_profile(
        workspace_id=context.workspace.id,
        policy_id=policy.id,
        body=body,
    )
    try:
        db.add(profile)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Tracked profile already exists",
            "This platform profile is already tracked in the workspace.",
        ) from exc
    return DataResponse(
        data=TrackedProfileRead.model_validate(profile),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/import",
    response_model=DataResponse[list[TrackedProfileRead]],
    status_code=status.HTTP_201_CREATED,
)
def import_profiles(
    body: TrackedProfileImportRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    requested_keys = [(item.platform, item.external_id) for item in body.profiles]
    if len(requested_keys) != len(set(requested_keys)):
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Duplicate tracked profile in request",
            "Each platform profile may appear only once in a batch import.",
        )
    profiles = []
    for item in body.profiles:
        _validate_platform(item.platform)
        policy = _scan_policy(
            db,
            workspace_id=context.workspace.id,
            scan_policy_id=item.scan_policy_id,
        )
        profile = _new_profile(
            workspace_id=context.workspace.id,
            policy_id=policy.id,
            body=item,
        )
        db.add(profile)
        profiles.append(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Tracked profile already exists",
            "One or more platform profiles are already tracked in the workspace.",
        ) from exc
    return DataResponse(
        data=[TrackedProfileRead.model_validate(item) for item in profiles],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{profile_id}", response_model=DataResponse[TrackedProfileRead])
def get_profile(
    profile_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    profile = _get_profile(db, context.workspace.id, profile_id)
    return DataResponse(
        data=TrackedProfileRead.model_validate(profile),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{profile_id}/contents",
    response_model=DataResponse[list[ExternalContentRead]],
)
def list_profile_contents(
    profile_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    _get_profile(db, context.workspace.id, profile_id)
    contents = db.scalars(
        select(ExternalContent)
        .where(
            ExternalContent.workspace_id == context.workspace.id,
            ExternalContent.tracked_profile_id == profile_id,
        )
        .order_by(
            ExternalContent.published_at.is_(None),
            ExternalContent.published_at.desc(),
            ExternalContent.first_seen_at.desc(),
        )
        .limit(limit)
    ).all()
    return DataResponse(
        data=[ExternalContentRead.model_validate(item) for item in contents],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{profile_id}/metrics",
    response_model=DataResponse[list[ProfileMetricSnapshotRead]],
)
def list_profile_metrics(
    profile_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    _get_profile(db, context.workspace.id, profile_id)
    snapshots = db.scalars(
        select(ProfileMetricSnapshot)
        .where(
            ProfileMetricSnapshot.workspace_id == context.workspace.id,
            ProfileMetricSnapshot.tracked_profile_id == profile_id,
        )
        .order_by(
            ProfileMetricSnapshot.captured_at.desc(),
            ProfileMetricSnapshot.id.desc(),
        )
        .limit(limit)
    ).all()
    return DataResponse(
        data=[ProfileMetricSnapshotRead.model_validate(item) for item in snapshots],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{profile_id}/sync-runs",
    response_model=DataResponse[list[JobRead]],
)
def list_profile_sync_runs(
    profile_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    _get_profile(db, context.workspace.id, profile_id)
    jobs = db.scalars(
        select(SyncJob)
        .where(
            SyncJob.workspace_id == context.workspace.id,
            SyncJob.job_type == "PROFILE_SCAN",
            SyncJob.payload["tracked_profile_id"].as_string() == str(profile_id),
        )
        .order_by(SyncJob.created_at.desc(), SyncJob.id.desc())
        .limit(limit)
    ).all()
    return DataResponse(
        data=[JobRead.model_validate(item) for item in jobs],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/{profile_id}", response_model=DataResponse[TrackedProfileRead])
def update_profile(
    profile_id: uuid.UUID,
    body: TrackedProfileUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    profile = _get_profile(db, context.workspace.id, profile_id)
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, name, value)
    db.commit()
    return DataResponse(
        data=TrackedProfileRead.model_validate(profile),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> None:
    profile = _get_profile(db, context.workspace.id, profile_id)
    profile.active = False
    profile.sync_status = "paused"
    profile.next_scan_at = None
    db.commit()


@router.post(
    "/{profile_id}/sync",
    response_model=DataResponse[JobAccepted],
    status_code=202,
)
def sync_profile(
    profile_id: uuid.UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    profile = _get_profile(db, context.workspace.id, profile_id)
    if not profile.active:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Profile is paused",
            "Resume the tracked profile before requesting a sync.",
        )
    dedupe_key = f"profile-sync:{profile.id}"
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="PROFILE_SCAN",
        dedupe_key=dedupe_key,
        payload={
            "tracked_profile_id": str(profile.id),
            "source": "manual",
        },
        priority=profile.priority,
    )
    db.commit()
    return DataResponse(
        data=JobAccepted(job_id=job.id, status=job.status),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{profile_id}/pause", response_model=DataResponse[TrackedProfileRead])
def pause_profile(
    profile_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    profile = _get_profile(db, context.workspace.id, profile_id)
    profile.active = False
    profile.sync_status = "paused"
    db.commit()
    return DataResponse(
        data=TrackedProfileRead.model_validate(profile),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{profile_id}/resume", response_model=DataResponse[TrackedProfileRead])
def resume_profile(
    profile_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    profile = _get_profile(db, context.workspace.id, profile_id)
    profile.active = True
    profile.sync_status = "idle"
    db.commit()
    return DataResponse(
        data=TrackedProfileRead.model_validate(profile),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
