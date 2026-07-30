import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    require_owner,
)
from app.core.errors import AppError
from app.db.models import AuditEvent, User, WorkspaceMember
from app.modules.identity.schemas import (
    AuditEventRead,
    UserRead,
    WorkspaceMemberAdd,
    WorkspaceMemberRead,
    WorkspaceMemberUpdate,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["members", "audit"])


def _ensure_workspace_path(
    workspace_id: uuid.UUID,
    context: WorkspaceContext,
) -> None:
    if workspace_id != context.workspace.id:
        raise AppError(
            403,
            "FORBIDDEN",
            "Access denied",
            "The workspace path does not match X-Workspace-Id.",
        )


def _member_read(member: WorkspaceMember, user: User) -> WorkspaceMemberRead:
    return WorkspaceMemberRead(
        id=member.id,
        user=UserRead.model_validate(user),
        role=member.role,
        created_at=member.created_at,
    )


def _get_member(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember:
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if member is None:
        raise AppError(404, "NOT_FOUND", "Member not found", "Member not found.")
    return member


def _ensure_not_last_owner(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    member: WorkspaceMember,
) -> None:
    if member.role != "owner":
        return
    owner_count = db.scalar(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == "owner",
        )
    )
    if owner_count == 1:
        raise AppError(
            409,
            "LAST_OWNER_REQUIRED",
            "Workspace requires an owner",
            "Add another owner before removing or demoting the last owner.",
        )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=DataResponse[list[WorkspaceMemberRead]],
)
def list_members(
    workspace_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DataResponse:
    _ensure_workspace_path(workspace_id, context)
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at)
    ).all()
    return DataResponse(
        data=[_member_read(member, user) for member, user in rows],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=DataResponse[WorkspaceMemberRead],
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    workspace_id: uuid.UUID,
    body: WorkspaceMemberAdd,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DataResponse:
    _ensure_workspace_path(workspace_id, context)
    user = db.scalar(
        select(User).where(
            User.id == body.user_id,
            User.status == "active",
        )
    )
    if user is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "User not found",
            "The user must sign in once before being added to a workspace.",
        )
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=body.role,
    )
    try:
        db.add(member)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Member already exists",
            "The user is already a member of this workspace.",
        ) from exc
    return DataResponse(
        data=_member_read(member, user),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=DataResponse[WorkspaceMemberRead],
)
def update_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: WorkspaceMemberUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DataResponse:
    _ensure_workspace_path(workspace_id, context)
    member = _get_member(db, workspace_id=workspace_id, user_id=user_id)
    if member.role == "owner" and body.role != "owner":
        _ensure_not_last_owner(db, workspace_id=workspace_id, member=member)
    member.role = body.role
    db.commit()
    user = db.get(User, user_id)
    return DataResponse(
        data=_member_read(member, user),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> Response:
    _ensure_workspace_path(workspace_id, context)
    member = _get_member(db, workspace_id=workspace_id, user_id=user_id)
    _ensure_not_last_owner(db, workspace_id=workspace_id, member=member)
    db.delete(member)
    db.commit()
    return Response(status_code=204)


@router.get(
    "/audit-events",
    response_model=DataResponse[list[AuditEventRead]],
)
def list_audit_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DataResponse:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == context.workspace.id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    ).all()
    return DataResponse(
        data=[AuditEventRead.model_validate(item) for item in events],
        meta=ResponseMeta(request_id=request.state.request_id),
    )
