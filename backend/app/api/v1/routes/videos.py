import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import VideoRun
from app.modules.video_production.schemas import VideoRunAccepted, VideoRunCreate, VideoRunRead
from app.modules.video_production.service import create_video_run
from app.modules.workflow.service import get_project
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/content-projects", tags=["videos"])


def _get_run(
    db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, run_id: uuid.UUID
) -> VideoRun:
    run = db.scalar(
        select(VideoRun).where(
            VideoRun.id == run_id,
            VideoRun.workspace_id == workspace_id,
            VideoRun.content_project_id == project_id,
        )
    )
    if run is None:
        raise AppError(404, "NOT_FOUND", "Video run not found", "Video run not found.")
    return run


@router.post(
    "/{project_id}/videos",
    response_model=DataResponse[VideoRunAccepted],
    status_code=status.HTTP_202_ACCEPTED,
)
def request_video(
    project_id: uuid.UUID,
    body: VideoRunCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    run, created = create_video_run(
        db,
        settings=settings,
        workspace_id=context.workspace.id,
        project_id=project_id,
        body=body,
        requested_by=context.membership.user_id,
    )
    return DataResponse(
        data=VideoRunAccepted(video_run=VideoRunRead.model_validate(run), reused=not created),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{project_id}/videos", response_model=DataResponse[list[VideoRunRead]])
def list_video_runs(
    project_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    get_project(db, workspace_id=context.workspace.id, project_id=project_id)
    runs = db.scalars(
        select(VideoRun)
        .where(
            VideoRun.workspace_id == context.workspace.id,
            VideoRun.content_project_id == project_id,
        )
        .order_by(VideoRun.created_at.desc())
    ).all()
    return DataResponse(
        data=[VideoRunRead.model_validate(run) for run in runs],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{project_id}/videos/{run_id}", response_model=DataResponse[VideoRunRead])
def get_video_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    run = _get_run(db, workspace_id=context.workspace.id, project_id=project_id, run_id=run_id)
    return DataResponse(
        data=VideoRunRead.model_validate(run),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{project_id}/videos/{run_id}/artifact")
def download_video_artifact(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: WorkspaceContext = Depends(get_workspace_context),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> FileResponse:
    run = _get_run(db, workspace_id=context.workspace.id, project_id=project_id, run_id=run_id)
    if run.status != "succeeded":
        raise AppError(
            409, "VIDEO_NOT_READY", "Video is not ready", "The video has not finished rendering."
        )
    root = Path(settings.video_runs_dir).expanduser().resolve()
    artifact = (root / str(run.id) / "final.mp4").resolve()
    if root not in artifact.parents or not artifact.is_file():
        raise AppError(
            404,
            "VIDEO_ARTIFACT_NOT_FOUND",
            "Video file not found",
            "The local artifact is unavailable.",
        )
    return FileResponse(artifact, media_type="video/mp4", filename=f"{run.id}.mp4")
