import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import ScriptVersion
from app.modules.workflow.schemas import (
    ScriptCreate,
    ScriptDuplicate,
    ScriptVersionRead,
)
from app.modules.workflow.service import get_project
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["scripts"])


@router.get(
    "/content-projects/{project_id}/scripts",
    response_model=DataResponse[list[ScriptVersionRead]],
)
def list_scripts(
    project_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    get_project(db, workspace_id=context.workspace.id, project_id=project_id)
    scripts = db.scalars(
        select(ScriptVersion)
        .where(
            ScriptVersion.workspace_id == context.workspace.id,
            ScriptVersion.content_project_id == project_id,
            ScriptVersion.deleted_at.is_(None),
        )
        .order_by(ScriptVersion.version_no.desc())
    ).all()
    return DataResponse(
        data=[ScriptVersionRead.model_validate(item) for item in scripts],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


def _append_script(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    project_version: int,
    body: str,
    structured_body: dict | None,
    change_note: str | None,
    created_by: uuid.UUID,
) -> ScriptVersion:
    project = get_project(
        db,
        workspace_id=workspace_id,
        project_id=project_id,
        for_update=True,
    )
    if project.version != project_version:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Content project was changed",
            "Reload the latest project before saving this script version.",
        )
    if project.status == "archived":
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Project is archived",
            "Archived projects cannot receive new script versions.",
        )
    latest_version = db.scalar(
        select(func.max(ScriptVersion.version_no)).where(
            ScriptVersion.content_project_id == project.id
        )
    )
    script = ScriptVersion(
        workspace_id=workspace_id,
        content_project_id=project.id,
        version_no=(latest_version or 0) + 1,
        body=body,
        structured_body=structured_body,
        change_note=change_note,
        created_by=created_by,
    )
    db.add(script)
    project.version += 1
    if project.status == "idea":
        project.status = "scripting"
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Script version conflict",
            "Another script version was saved first. Reload and retry.",
        ) from exc
    return script


@router.post(
    "/content-projects/{project_id}/scripts",
    response_model=DataResponse[ScriptVersionRead],
    status_code=status.HTTP_201_CREATED,
)
def create_script(
    project_id: uuid.UUID,
    body: ScriptCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    script = _append_script(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
        project_version=body.project_version,
        body=body.body,
        structured_body=body.structured_body,
        change_note=body.change_note,
        created_by=context.membership.user_id,
    )
    return DataResponse(
        data=ScriptVersionRead.model_validate(script),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/scripts/{script_version_id}",
    response_model=DataResponse[ScriptVersionRead],
)
def get_script(
    script_version_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    script = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.workspace_id == context.workspace.id,
            ScriptVersion.id == script_version_id,
            ScriptVersion.deleted_at.is_(None),
        )
    )
    if script is None:
        raise AppError(404, "NOT_FOUND", "Script not found", "Script version not found.")
    return DataResponse(
        data=ScriptVersionRead.model_validate(script),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/content-projects/{project_id}/scripts/{version_no}/duplicate",
    response_model=DataResponse[ScriptVersionRead],
    status_code=status.HTTP_201_CREATED,
)
def duplicate_script(
    project_id: uuid.UUID,
    version_no: int,
    body: ScriptDuplicate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    source = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.workspace_id == context.workspace.id,
            ScriptVersion.content_project_id == project_id,
            ScriptVersion.version_no == version_no,
            ScriptVersion.deleted_at.is_(None),
        )
    )
    if source is None:
        raise AppError(404, "NOT_FOUND", "Script not found", "Script version not found.")
    script = _append_script(
        db,
        workspace_id=context.workspace.id,
        project_id=project_id,
        project_version=body.project_version,
        body=source.body,
        structured_body=source.structured_body,
        change_note=body.change_note or f"Duplicated from version {version_no}",
        created_by=context.membership.user_id,
    )
    return DataResponse(
        data=ScriptVersionRead.model_validate(script),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
