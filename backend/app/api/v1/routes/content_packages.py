import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.config import Settings
from app.modules.content_packages.schemas import (
    ContentPackageEdit,
    ContentPackageGenerateRequest,
    ContentPackageRead,
)
from app.modules.content_packages.service import (
    content_package_read,
    edit_content_package,
    freeze_content_package,
    get_content_package,
    list_content_packages,
)
from app.modules.generation.schemas import GenerationAccepted, GenerationRunRead
from app.modules.generation.service import request_content_package_generation
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["content-packages"])


@router.post(
    "/content-projects/{project_id}/content-packages",
    response_model=DataResponse[GenerationAccepted],
)
def generate_content_package(
    project_id: uuid.UUID,
    body: ContentPackageGenerateRequest,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    run, reused = request_content_package_generation(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
        project_version=body.project_version,
        script_version_id=body.script_version_id,
        target_platform=body.target_platform,
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
    "/content-projects/{project_id}/content-packages",
    response_model=DataResponse[list[ContentPackageRead]],
)
def list_project_content_packages(
    project_id: uuid.UUID,
    request: Request,
    target_platform: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    packages = list_content_packages(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
        target_platform=target_platform,
    )
    return DataResponse(
        data=[content_package_read(item) for item in packages],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/content-packages/{package_id}",
    response_model=DataResponse[ContentPackageRead],
)
def get_single_content_package(
    package_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    package = get_content_package(
        db,
        workspace_id=context.workspace.id,
        package_id=package_id,
    )
    return DataResponse(
        data=content_package_read(package),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch(
    "/content-packages/{package_id}",
    response_model=DataResponse[ContentPackageRead],
)
def patch_content_package(
    package_id: uuid.UUID,
    body: ContentPackageEdit,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    package = edit_content_package(
        db,
        workspace_id=context.workspace.id,
        package_id=package_id,
        body=body,
        edited_by=context.membership.user_id,
    )
    db.commit()
    db.refresh(package)
    return DataResponse(
        data=content_package_read(package),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/content-packages/{package_id}/freeze",
    response_model=DataResponse[ContentPackageRead],
)
def freeze_single_content_package(
    package_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    package = freeze_content_package(
        db,
        workspace_id=context.workspace.id,
        package_id=package_id,
    )
    db.commit()
    db.refresh(package)
    return DataResponse(
        data=content_package_read(package),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
