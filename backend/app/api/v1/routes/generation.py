import uuid

from fastapi import APIRouter, Depends, Request, Response
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
from app.db.models import GenerationRun
from app.modules.generation.schemas import (
    GenerationAccepted,
    GenerationRunRead,
    ReviewGenerateRequest,
    ScriptGenerateRequest,
)
from app.modules.generation.service import (
    request_review_generation,
    request_script_generation,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["generation"])


@router.post(
    "/content-projects/{project_id}/scripts/generate",
    response_model=DataResponse[GenerationAccepted],
)
def generate_script(
    project_id: uuid.UUID,
    body: ScriptGenerateRequest,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    run, reused = request_script_generation(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
        project_version=body.project_version,
        instruction=body.instruction,
        force=body.force,
        requested_by=context.membership.user_id,
        settings=settings,
    )
    db.commit()
    response.status_code = 200 if reused and run.status == "succeeded" else 202
    return DataResponse(
        data=GenerationAccepted(
            generation=GenerationRunRead.model_validate(run),
            reused=reused,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-records/{record_id}/reviews/generate",
    response_model=DataResponse[GenerationAccepted],
)
def generate_review(
    record_id: uuid.UUID,
    body: ReviewGenerateRequest,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    run, reused = request_review_generation(
        db,
        workspace_id=context.workspace.id,
        publish_record_id=record_id,
        review_window=body.review_window,
        metrics=body.metrics,
        primary_metric=body.primary_metric,
        force=body.force,
        requested_by=context.membership.user_id,
        settings=settings,
    )
    db.commit()
    response.status_code = 200 if reused and run.status == "succeeded" else 202
    return DataResponse(
        data=GenerationAccepted(
            generation=GenerationRunRead.model_validate(run),
            reused=reused,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/generation-runs/{generation_run_id}",
    response_model=DataResponse[GenerationRunRead],
)
def get_generation_run(
    generation_run_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    run = db.scalar(
        select(GenerationRun).where(
            GenerationRun.workspace_id == context.workspace.id,
            GenerationRun.id == generation_run_id,
        )
    )
    if run is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Generation run not found",
            "Generation run not found.",
        )
    return DataResponse(
        data=GenerationRunRead.model_validate(run),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
