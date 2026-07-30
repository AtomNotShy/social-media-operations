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
from app.modules.workflow.schemas import (
    OwnedChannelCreate,
    OwnedChannelRead,
    OwnedChannelUpdate,
    PositioningUpdate,
)
from app.modules.workflow.service import get_owned_channel
from app.schemas.common import DataResponse, ResponseMeta

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
