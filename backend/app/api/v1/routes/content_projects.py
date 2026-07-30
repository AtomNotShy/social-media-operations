import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import ContentProject
from app.modules.workflow.schemas import (
    ContentProjectCreate,
    ContentProjectRead,
    ContentProjectUpdate,
    ProjectTransition,
)
from app.modules.workflow.service import (
    PROJECT_TRANSITIONS,
    get_owned_channel,
    get_project,
    get_topic,
    update_project_versioned,
    validate_workspace_user,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/content-projects", tags=["content-projects"])


@router.get("", response_model=DataResponse[list[ContentProjectRead]])
def list_projects(
    request: Request,
    status_filter: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(ContentProject).where(
        ContentProject.workspace_id == context.workspace.id,
        ContentProject.deleted_at.is_(None),
    )
    if status_filter:
        query = query.where(ContentProject.status == status_filter)
    projects = db.scalars(
        query.order_by(ContentProject.updated_at.desc(), ContentProject.id.desc())
    ).all()
    return DataResponse(
        data=[ContentProjectRead.model_validate(item) for item in projects],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "",
    response_model=DataResponse[ContentProjectRead],
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    body: ContentProjectCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=body.owned_channel_id,
        active_only=True,
    )
    if body.topic_id is not None:
        get_topic(db, workspace_id=context.workspace.id, topic_id=body.topic_id)
    validate_workspace_user(
        db,
        workspace_id=context.workspace.id,
        user_id=body.owner_user_id,
    )
    project = ContentProject(
        workspace_id=context.workspace.id,
        **body.model_dump(),
    )
    db.add(project)
    db.commit()
    return DataResponse(
        data=ContentProjectRead.model_validate(project),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{project_id}", response_model=DataResponse[ContentProjectRead])
def get_project_route(
    project_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    project = get_project(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
    )
    return DataResponse(
        data=ContentProjectRead.model_validate(project),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/{project_id}", response_model=DataResponse[ContentProjectRead])
def update_project(
    project_id: uuid.UUID,
    body: ContentProjectUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    project = get_project(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
    )
    values = body.model_dump(exclude={"version"}, exclude_unset=True)
    if "owner_user_id" in values:
        validate_workspace_user(
            db,
            workspace_id=context.workspace.id,
            user_id=values["owner_user_id"],
        )
    project = update_project_versioned(
        db,
        project=project,
        expected_version=body.version,
        values=values,
    )
    return DataResponse(
        data=ContentProjectRead.model_validate(project),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{project_id}/transition",
    response_model=DataResponse[ContentProjectRead],
)
def transition_project(
    project_id: uuid.UUID,
    body: ProjectTransition,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    project = get_project(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
    )
    if project.status != body.from_status:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Project status changed",
            f"Expected {body.from_status}, but the project is {project.status}.",
        )
    if body.to_status not in PROJECT_TRANSITIONS.get(body.from_status, set()):
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Invalid project transition",
            f"Cannot transition from {body.from_status} to {body.to_status}.",
        )
    project = update_project_versioned(
        db,
        project=project,
        expected_version=body.version,
        values={"status": body.to_status},
    )
    return DataResponse(
        data=ContentProjectRead.model_validate(project),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
