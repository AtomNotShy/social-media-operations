import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import WorkspaceContext, get_db, get_workspace_context, require_editor
from app.core.errors import AppError
from app.db.models import SyncJob
from app.jobs.schemas import JobRead
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _get_job(db: Session, workspace_id: uuid.UUID, job_id: uuid.UUID) -> SyncJob:
    job = db.scalar(
        select(SyncJob).where(
            SyncJob.workspace_id == workspace_id,
            SyncJob.id == job_id,
        )
    )
    if job is None:
        raise AppError(404, "NOT_FOUND", "Job not found", "Job not found.")
    return job


@router.get("", response_model=DataResponse[list[JobRead]])
def list_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(SyncJob).where(SyncJob.workspace_id == context.workspace.id)
    if status:
        query = query.where(SyncJob.status == status)
    jobs = db.scalars(query.order_by(SyncJob.created_at.desc()).limit(limit)).all()
    return DataResponse(
        data=[JobRead.model_validate(job) for job in jobs],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{job_id}", response_model=DataResponse[JobRead])
def get_job(
    job_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    job = _get_job(db, context.workspace.id, job_id)
    return DataResponse(
        data=JobRead.model_validate(job),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{job_id}/cancel", response_model=DataResponse[JobRead])
def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    job = _get_job(db, context.workspace.id, job_id)
    if job.status not in {"pending", "retry_wait"}:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Job cannot be cancelled",
            "Only pending or retry-wait jobs can be cancelled.",
        )
    job.status = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    return DataResponse(
        data=JobRead.model_validate(job),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{job_id}/retry", response_model=DataResponse[JobRead])
def retry_job(
    job_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    job = _get_job(db, context.workspace.id, job_id)
    if job.status not in {"failed", "dead"}:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Job cannot be retried",
            "Only failed or dead jobs can be retried.",
        )
    job.status = "pending"
    job.run_after = datetime.now(timezone.utc)
    job.finished_at = None
    job.locked_at = None
    job.locked_by = None
    db.commit()
    return DataResponse(
        data=JobRead.model_validate(job),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
