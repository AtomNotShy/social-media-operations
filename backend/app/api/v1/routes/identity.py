import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.errors import AppError
from app.db.models import ScanPolicy, ScoringPolicy, User, Workspace, WorkspaceMember
from app.modules.automation.schemas import AutomationSettings
from app.modules.identity.schemas import (
    ExternalCallsPauseRequest,
    ExternalCallsStateRead,
    MembershipRead,
    MeRead,
    UserRead,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["identity"])


def _workspace_membership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[Workspace, WorkspaceMember]:
    row = db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).one_or_none()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Workspace not found", "Workspace not found.")
    return row[0], row[1]


@router.get("/me", response_model=DataResponse[MeRead])
def me(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    memberships = db.scalars(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    ).all()
    data = MeRead(
        user=UserRead.model_validate(user),
        memberships=[
            MembershipRead(workspace_id=item.workspace_id, role=item.role) for item in memberships
        ],
    )
    return DataResponse(data=data, meta=ResponseMeta(request_id=request.state.request_id))


@router.get("/workspaces", response_model=DataResponse[list[WorkspaceRead]])
def list_workspaces(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    workspaces = db.scalars(
        select(Workspace)
        .join(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at)
    ).all()
    return DataResponse(
        data=[WorkspaceRead.model_validate(item) for item in workspaces],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/workspaces",
    response_model=DataResponse[WorkspaceRead],
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    body: WorkspaceCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    workspace = Workspace(
        name=body.name,
        timezone=body.timezone,
        daily_provider_budget_usd=body.daily_provider_budget_usd,
        daily_ai_budget_usd=body.daily_ai_budget_usd,
        settings={"automation": AutomationSettings().model_dump(mode="json")},
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    db.add(
        ScanPolicy(
            workspace_id=workspace.id,
            name="默认扫描策略",
            schedule={"interval_hours": 24},
            max_pages=2,
            detail_policy={"mode": "progressive"},
            metric_refresh_policy={"recent_hours": 12},
            comment_policy={"max_pages": 1},
        )
    )
    db.add(
        ScoringPolicy(
            workspace_id=workspace.id,
            platform="xiaohongshu",
            version=1,
            core_metric_formula={
                "required_metrics": ["likes", "comments", "favorites"],
                "core_metric_weights": {
                    "likes": 1,
                    "comments": 2,
                    "favorites": 2,
                    "shares": 3,
                },
                "reach_proxy_weights": {
                    "likes": 1,
                    "comments": 2,
                    "favorites": 2,
                    "shares": 3,
                },
            },
            tier_thresholds={
                "micro_max": 10000,
                "small_max": 100000,
                "medium_max": 1000000,
            },
            grade_thresholds={
                "t1": {"minimum_r": 5, "minimum_m": 0.1},
                "t2": {"minimum_r": 3, "minimum_m": 0.05},
                "t3": {"minimum_r": 2, "minimum_m": 0},
                "low_quality": {"maximum_r": 0.5},
            },
            minimum_age_minutes=60,
            minimum_baseline_count=5,
            active=True,
        )
    )
    db.add(
        ScoringPolicy(
            workspace_id=workspace.id,
            platform="x",
            version=1,
            core_metric_formula={
                "required_metrics": ["likes", "comments", "favorites"],
                "core_metric_weights": {
                    "likes": 1,
                    "comments": 2,
                    "favorites": 2,
                    "shares": 3,
                },
                "reach_proxy_weights": {
                    "likes": 1,
                    "comments": 2,
                    "favorites": 2,
                    "shares": 3,
                },
            },
            tier_thresholds={
                "micro_max": 10000,
                "small_max": 100000,
                "medium_max": 1000000,
            },
            grade_thresholds={
                "t1": {"minimum_r": 5, "minimum_m": 0.1},
                "t2": {"minimum_r": 3, "minimum_m": 0.05},
                "t3": {"minimum_r": 2, "minimum_m": 0},
                "low_quality": {"maximum_r": 0.5},
            },
            minimum_age_minutes=60,
            minimum_baseline_count=5,
            active=True,
        )
    )
    db.commit()
    return DataResponse(
        data=WorkspaceRead.model_validate(workspace),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


def _set_external_calls_paused(
    *,
    workspace_id: uuid.UUID,
    paused: bool,
    reason: str | None,
    request: Request,
    user: User,
    db: Session,
) -> DataResponse:
    _, membership = _workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
    )
    if membership.role != "owner":
        raise AppError(
            403,
            "FORBIDDEN",
            "Access denied",
            "Only workspace owners can change the external-call emergency stop.",
        )
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
    if workspace is None:
        raise AppError(404, "NOT_FOUND", "Workspace not found", "Workspace not found.")
    changed_at = datetime.now(timezone.utc)
    settings = dict(workspace.settings)
    settings["external_calls"] = {
        "paused": paused,
        "reason": reason,
        "changed_at": changed_at.isoformat(),
        "changed_by": str(user.id),
    }
    workspace.settings = settings
    db.commit()
    return DataResponse(
        data=ExternalCallsStateRead(
            paused=paused,
            reason=reason,
            changed_at=changed_at,
            changed_by=user.id,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/workspaces/{workspace_id}/external-calls/pause",
    response_model=DataResponse[ExternalCallsStateRead],
)
def pause_external_calls(
    workspace_id: uuid.UUID,
    body: ExternalCallsPauseRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    return _set_external_calls_paused(
        workspace_id=workspace_id,
        paused=True,
        reason=body.reason,
        request=request,
        user=user,
        db=db,
    )


@router.post(
    "/workspaces/{workspace_id}/external-calls/resume",
    response_model=DataResponse[ExternalCallsStateRead],
)
def resume_external_calls(
    workspace_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    return _set_external_calls_paused(
        workspace_id=workspace_id,
        paused=False,
        reason=None,
        request=request,
        user=user,
        db=db,
    )


@router.get(
    "/workspaces/{workspace_id}",
    response_model=DataResponse[WorkspaceRead],
)
def get_workspace(
    workspace_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    workspace, _ = _workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
    )
    return DataResponse(
        data=WorkspaceRead.model_validate(workspace),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch(
    "/workspaces/{workspace_id}",
    response_model=DataResponse[WorkspaceRead],
)
def update_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    workspace, membership = _workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
    )
    if membership.role != "owner":
        raise AppError(
            403,
            "FORBIDDEN",
            "Access denied",
            "Only workspace owners can update workspace settings and budgets.",
        )
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(workspace, name, value)
    db.commit()
    return DataResponse(
        data=WorkspaceRead.model_validate(workspace),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
