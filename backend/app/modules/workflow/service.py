import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import ContentProject, OwnedChannel, Topic, User, WorkspaceMember

PROJECT_TRANSITIONS = {
    "idea": {"scripting", "archived"},
    "scripting": {"producing", "archived"},
    "producing": {"scripting", "review", "archived"},
    "review": {"producing", "scheduled", "archived"},
    "scheduled": {"review", "published", "archived"},
    "published": {"reviewing", "archived"},
    "reviewing": {"archived"},
    "archived": set(),
}


def get_owned_channel(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    channel_id: uuid.UUID,
    active_only: bool = False,
) -> OwnedChannel:
    query = select(OwnedChannel).where(
        OwnedChannel.workspace_id == workspace_id,
        OwnedChannel.id == channel_id,
    )
    if active_only:
        query = query.where(OwnedChannel.active.is_(True))
    channel = db.scalar(query)
    if channel is None:
        raise AppError(404, "NOT_FOUND", "Owned channel not found", "Channel not found.")
    return channel


def get_topic(db: Session, *, workspace_id: uuid.UUID, topic_id: uuid.UUID) -> Topic:
    topic = db.scalar(
        select(Topic).where(
            Topic.workspace_id == workspace_id,
            Topic.id == topic_id,
            Topic.deleted_at.is_(None),
        )
    )
    if topic is None:
        raise AppError(404, "NOT_FOUND", "Topic not found", "Topic not found.")
    return topic


def get_project(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    for_update: bool = False,
) -> ContentProject:
    query = select(ContentProject).where(
        ContentProject.workspace_id == workspace_id,
        ContentProject.id == project_id,
        ContentProject.deleted_at.is_(None),
    )
    if for_update:
        query = query.with_for_update()
    project = db.scalar(query)
    if project is None:
        raise AppError(404, "NOT_FOUND", "Content project not found", "Project not found.")
    return project


def validate_workspace_user(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> None:
    if user_id is None:
        return
    exists = db.scalar(
        select(User.id)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            User.id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    if exists is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid project owner",
            "The owner must be a member of the current workspace.",
        )


def update_topic_versioned(
    db: Session,
    *,
    topic: Topic,
    expected_version: int,
    values: dict,
) -> Topic:
    result = db.execute(
        update(Topic)
        .where(
            Topic.id == topic.id,
            Topic.workspace_id == topic.workspace_id,
            Topic.version == expected_version,
            Topic.deleted_at.is_(None),
        )
        .values(**values, version=Topic.version + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Topic was changed",
            "Reload the latest topic before saving your changes.",
        )
    db.commit()
    return get_topic(db, workspace_id=topic.workspace_id, topic_id=topic.id)


def update_project_versioned(
    db: Session,
    *,
    project: ContentProject,
    expected_version: int,
    values: dict,
) -> ContentProject:
    result = db.execute(
        update(ContentProject)
        .where(
            ContentProject.id == project.id,
            ContentProject.workspace_id == project.workspace_id,
            ContentProject.version == expected_version,
            ContentProject.deleted_at.is_(None),
        )
        .values(**values, version=ContentProject.version + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Content project was changed",
            "Reload the latest project before saving your changes.",
        )
    db.commit()
    return get_project(db, workspace_id=project.workspace_id, project_id=project.id)
