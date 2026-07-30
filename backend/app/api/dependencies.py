import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import authenticate_token
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import User, Workspace, WorkspaceMember

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    workspace: Workspace
    membership: WorkspaceMember


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.database.session()


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            401,
            "UNAUTHENTICATED",
            "Authentication required",
            "A bearer access token is required.",
        )
    identity = authenticate_token(credentials.credentials, settings)
    user = db.scalar(select(User).where(User.external_subject == identity.subject))
    if user is None:
        user = User(
            external_subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name or identity.email or identity.subject,
        )
        db.add(user)
        db.commit()
    if user.status != "active":
        raise AppError(403, "FORBIDDEN", "Access denied", "The user is disabled.")
    request.state.current_user_id = user.id
    return user


def get_workspace_context(
    request: Request,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceContext:
    if not x_workspace_id:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Workspace header required",
            "X-Workspace-Id is required for this endpoint.",
        )
    try:
        workspace_id = uuid.UUID(x_workspace_id)
    except ValueError as exc:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid workspace header",
            "X-Workspace-Id must be a UUID.",
        ) from exc
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        raise AppError(403, "FORBIDDEN", "Access denied", "Workspace access is denied.")
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise AppError(404, "NOT_FOUND", "Workspace not found", "Workspace not found.")
    request.state.workspace_id = workspace.id
    return WorkspaceContext(workspace=workspace, membership=membership)


def require_editor(
    context: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    if context.membership.role not in {"owner", "editor"}:
        raise AppError(
            403,
            "FORBIDDEN",
            "Access denied",
            "This action requires the owner or editor role.",
        )
    return context


def require_owner(
    context: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    if context.membership.role != "owner":
        raise AppError(
            403,
            "FORBIDDEN",
            "Access denied",
            "This action requires the workspace owner role.",
        )
    return context
