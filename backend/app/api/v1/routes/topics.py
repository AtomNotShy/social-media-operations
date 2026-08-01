import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.db.models import Topic, WorkspaceInspiration
from app.modules.analysis.service import inspiration_content
from app.modules.workflow.schemas import (
    TopicCreate,
    TopicFromInspiration,
    TopicRead,
    TopicUpdate,
)
from app.modules.workflow.service import (
    get_owned_channel,
    get_topic,
    update_topic_versioned,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/topics", tags=["topics"])


@router.get("", response_model=DataResponse[list[TopicRead]])
def list_topics(
    request: Request,
    status_filter: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(Topic).where(
        Topic.workspace_id == context.workspace.id,
        Topic.deleted_at.is_(None),
    )
    if status_filter:
        query = query.where(Topic.status == status_filter)
    topics = db.scalars(query.order_by(Topic.updated_at.desc(), Topic.id.desc())).all()
    return DataResponse(
        data=[TopicRead.model_validate(item) for item in topics],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "",
    response_model=DataResponse[TopicRead],
    status_code=status.HTTP_201_CREATED,
)
def create_topic(
    body: TopicCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    if body.owned_channel_id is not None:
        get_owned_channel(
            db,
            workspace_id=context.workspace.id,
            channel_id=body.owned_channel_id,
            active_only=True,
        )
    topic = Topic(
        workspace_id=context.workspace.id,
        created_by=context.membership.user_id,
        **body.model_dump(),
    )
    db.add(topic)
    db.commit()
    return DataResponse(
        data=TopicRead.model_validate(topic),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/from-inspiration/{inspiration_id}",
    response_model=DataResponse[TopicRead],
    status_code=status.HTTP_201_CREATED,
)
def create_topic_from_inspiration(
    inspiration_id: uuid.UUID,
    body: TopicFromInspiration,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    content = inspiration_content(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    if body.owned_channel_id is not None:
        get_owned_channel(
            db,
            workspace_id=context.workspace.id,
            channel_id=body.owned_channel_id,
            active_only=True,
        )
    title = body.title or content.title or content.body_text
    if not title:
        title = f"{content.platform} content {content.external_id}"
    topic = Topic(
        workspace_id=context.workspace.id,
        owned_channel_id=body.owned_channel_id,
        title=title[:500],
        audience_problem=body.audience_problem,
        angle=body.angle,
        hook=body.hook,
        evidence_refs=[
            f"inspiration:{inspiration_id}",
            f"content:{content.id}",
        ],
        created_by=context.membership.user_id,
    )
    db.add(topic)
    inspiration = db.scalar(
        select(WorkspaceInspiration).where(
            WorkspaceInspiration.workspace_id == context.workspace.id,
            WorkspaceInspiration.id == inspiration_id,
        )
    )
    # The topic and its source now belong to the same workflow stage. Keeping
    # this in the transaction prevents a created topic from leaving its source
    # looking like an unreviewed inbox item.
    if inspiration is not None:
        inspiration.status = "candidate"
    db.commit()
    return DataResponse(
        data=TopicRead.model_validate(topic),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{topic_id}", response_model=DataResponse[TopicRead])
def get_topic_route(
    topic_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    topic = get_topic(db, workspace_id=context.workspace.id, topic_id=topic_id)
    return DataResponse(
        data=TopicRead.model_validate(topic),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/{topic_id}", response_model=DataResponse[TopicRead])
def update_topic(
    topic_id: uuid.UUID,
    body: TopicUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    topic = get_topic(db, workspace_id=context.workspace.id, topic_id=topic_id)
    values = body.model_dump(exclude={"version"}, exclude_unset=True)
    if "owned_channel_id" in values and values["owned_channel_id"] is not None:
        get_owned_channel(
            db,
            workspace_id=context.workspace.id,
            channel_id=values["owned_channel_id"],
            active_only=True,
        )
    topic = update_topic_versioned(
        db,
        topic=topic,
        expected_version=body.version,
        values=values,
    )
    return DataResponse(
        data=TopicRead.model_validate(topic),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete("/{topic_id}", response_model=DataResponse[TopicRead])
def delete_topic(
    topic_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    topic = get_topic(db, workspace_id=context.workspace.id, topic_id=topic_id)
    topic.status = "archived"
    topic.deleted_at = datetime.now(timezone.utc)
    topic.version += 1
    db.commit()
    return DataResponse(
        data=TopicRead.model_validate(topic),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
