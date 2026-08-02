import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import OwnedChannel
from app.jobs.service import create_job
from app.modules.workflow.schemas import (
    OwnedChannelCreate,
    OwnedChannelRead,
    OwnedChannelUpdate,
    PositioningUpdate,
)
from app.modules.workflow.service import get_owned_channel
from app.schemas.common import DataResponse, JobAccepted, ResponseMeta

router = APIRouter(prefix="/api/v1/owned-channels", tags=["owned-channels"])


@router.get("", response_model=DataResponse[list[OwnedChannelRead]])
def list_channels(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    channels = db.scalars(
        select(OwnedChannel)
        .where(OwnedChannel.workspace_id == context.workspace.id)
        .order_by(OwnedChannel.created_at, OwnedChannel.id)
    ).all()
    return DataResponse(
        data=[OwnedChannelRead.model_validate(item) for item in channels],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "",
    response_model=DataResponse[OwnedChannelRead],
    status_code=status.HTTP_201_CREATED,
)
def create_channel(
    body: OwnedChannelCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    channel = OwnedChannel(
        workspace_id=context.workspace.id,
        **body.model_dump(),
    )
    try:
        db.add(channel)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Owned channel already exists",
            "This platform account already exists in the workspace.",
        ) from exc
    if channel.external_id:
        create_job(
            db,
            workspace_id=context.workspace.id,
            job_type="OWNED_CHANNEL_SCAN",
            dedupe_key=f"owned-channel-scan:{channel.id}",
            payload={
                "owned_channel_id": str(channel.id),
                "source": "create",
            },
        )
        channel.sync_status = "pending"
        db.commit()
    return DataResponse(
        data=OwnedChannelRead.model_validate(channel),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{channel_id}", response_model=DataResponse[OwnedChannelRead])
def get_channel(
    channel_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    channel = get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=channel_id,
    )
    return DataResponse(
        data=OwnedChannelRead.model_validate(channel),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/{channel_id}/scan",
    response_model=DataResponse[JobAccepted],
    status_code=status.HTTP_202_ACCEPTED,
)
def scan_channel(
    channel_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    channel = get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=channel_id,
    )
    if not channel.active:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Channel is disabled",
            "Re-enable the channel before requesting a scan.",
        )
    if not channel.external_id:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Platform account ID is required",
            "Set the platform account ID before requesting a scan.",
        )
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="OWNED_CHANNEL_SCAN",
        dedupe_key=f"owned-channel-scan:{channel.id}",
        payload={
            "owned_channel_id": str(channel.id),
            "source": "manual",
        },
    )
    channel.sync_status = "syncing" if job.status == "running" else "pending"
    db.commit()
    return DataResponse(
        data=JobAccepted(job_id=job.id, status=job.status),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/{channel_id}", response_model=DataResponse[OwnedChannelRead])
def update_channel(
    channel_id: uuid.UUID,
    body: OwnedChannelUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    channel = get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=channel_id,
    )
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(channel, name, value)
    db.commit()
    return DataResponse(
        data=OwnedChannelRead.model_validate(channel),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete("/{channel_id}", response_model=DataResponse[OwnedChannelRead])
def disable_channel(
    channel_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    channel = get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=channel_id,
    )
    channel.active = False
    channel.publishing_mode = "disabled"
    db.commit()
    return DataResponse(
        data=OwnedChannelRead.model_validate(channel),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/{channel_id}/positioning",
    response_model=DataResponse[OwnedChannelRead],
)
def get_positioning(
    channel_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    return get_channel(channel_id, request, context, db)


@router.put(
    "/{channel_id}/positioning",
    response_model=DataResponse[OwnedChannelRead],
)
def update_positioning(
    channel_id: uuid.UUID,
    body: PositioningUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    channel = get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=channel_id,
    )
    for name, value in body.model_dump().items():
        setattr(channel, name, value)
    db.commit()
    return DataResponse(
        data=OwnedChannelRead.model_validate(channel),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
