import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import (
    Asset,
    ContentProject,
    PublishPlan,
    PublishRecord,
    ReviewInsight,
    ScriptVersion,
)
from app.modules.workflow.schemas import (
    MarkPublishedRequest,
    PublishPackage,
    PublishPlanCreate,
    PublishPlanRead,
    PublishPlanUpdate,
    PublishRecordRead,
    ReviewCreate,
    ReviewInsightRead,
    ScriptVersionRead,
)
from app.modules.workflow.service import get_owned_channel, get_project
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["publishing"])


def _get_plan(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> PublishPlan:
    plan = db.scalar(
        select(PublishPlan).where(
            PublishPlan.workspace_id == workspace_id,
            PublishPlan.id == plan_id,
        )
    )
    if plan is None:
        raise AppError(404, "NOT_FOUND", "Publish plan not found", "Plan not found.")
    return plan


def _get_record(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    record_id: uuid.UUID,
) -> PublishRecord:
    record = db.scalar(
        select(PublishRecord).where(
            PublishRecord.workspace_id == workspace_id,
            PublishRecord.id == record_id,
        )
    )
    if record is None:
        raise AppError(404, "NOT_FOUND", "Publish record not found", "Record not found.")
    return record


def _plan_version_conflict() -> AppError:
    return AppError(
        409,
        "VERSION_CONFLICT",
        "Publish plan was changed",
        "Reload the latest publish plan before saving changes.",
    )


@router.get("/publish-plans", response_model=DataResponse[list[PublishPlanRead]])
def list_publish_plans(
    request: Request,
    status_filter: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(PublishPlan).where(PublishPlan.workspace_id == context.workspace.id)
    if status_filter:
        query = query.where(PublishPlan.status == status_filter)
    plans = db.scalars(query.order_by(PublishPlan.scheduled_at, PublishPlan.id)).all()
    return DataResponse(
        data=[PublishPlanRead.model_validate(item) for item in plans],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-plans",
    response_model=DataResponse[PublishPlanRead],
    status_code=status.HTTP_201_CREATED,
)
def create_publish_plan(
    body: PublishPlanCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    project = get_project(
        db,
        workspace_id=context.workspace.id,
        project_id=body.content_project_id,
    )
    channel = get_owned_channel(
        db,
        workspace_id=context.workspace.id,
        channel_id=body.owned_channel_id,
        active_only=True,
    )
    if project.owned_channel_id != channel.id:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Channel mismatch",
            "The publish channel must match the content project channel.",
        )
    if body.publishing_mode != "manual":
        raise AppError(
            409,
            "UNSUPPORTED_PLATFORM_CAPABILITY",
            "Official publishing is not enabled",
            "The MVP only generates manual publishing packages.",
        )
    plan = PublishPlan(
        workspace_id=context.workspace.id,
        **body.model_dump(),
    )
    db.add(plan)
    db.commit()
    return DataResponse(
        data=PublishPlanRead.model_validate(plan),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/publish-plans/{plan_id}",
    response_model=DataResponse[PublishPlanRead],
)
def get_publish_plan(
    plan_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan_id)
    return DataResponse(
        data=PublishPlanRead.model_validate(plan),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch(
    "/publish-plans/{plan_id}",
    response_model=DataResponse[PublishPlanRead],
)
def update_publish_plan(
    plan_id: uuid.UUID,
    body: PublishPlanUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan_id)
    if plan.status in {"published", "cancelled"}:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Publish plan is final",
            "Published or cancelled plans cannot be edited.",
        )
    values = body.model_dump(exclude={"version"}, exclude_unset=True)
    if plan.status != "draft" and values:
        values.update(
            status="draft",
            approved_by=None,
            approved_at=None,
        )
    result = db.execute(
        update(PublishPlan)
        .where(
            PublishPlan.id == plan.id,
            PublishPlan.workspace_id == context.workspace.id,
            PublishPlan.version == body.version,
        )
        .values(**values, version=PublishPlan.version + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise _plan_version_conflict()
    db.commit()
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan.id)
    return DataResponse(
        data=PublishPlanRead.model_validate(plan),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-plans/{plan_id}/approve",
    response_model=DataResponse[PublishPlanRead],
)
def approve_publish_plan(
    plan_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan_id)
    project = get_project(
        db,
        workspace_id=context.workspace.id,
        project_id=plan.content_project_id,
        for_update=True,
    )
    if plan.status != "draft":
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Plan is not a draft",
            "Only draft plans can be approved.",
        )
    if project.status != "review":
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Project is not ready",
            "The content project must be in review before approval.",
        )
    latest_script = db.scalar(
        select(ScriptVersion.id)
        .where(
            ScriptVersion.workspace_id == context.workspace.id,
            ScriptVersion.content_project_id == project.id,
            ScriptVersion.deleted_at.is_(None),
        )
        .limit(1)
    )
    if latest_script is None:
        raise AppError(
            409,
            "PUBLISH_PACKAGE_INCOMPLETE",
            "Script is missing",
            "At least one script version is required before approval.",
        )
    plan.status = "approved"
    plan.approved_by = context.membership.user_id
    plan.approved_at = datetime.now(timezone.utc)
    plan.version += 1
    project.status = "scheduled"
    project.version += 1
    db.commit()
    return DataResponse(
        data=PublishPlanRead.model_validate(plan),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-plans/{plan_id}/cancel",
    response_model=DataResponse[PublishPlanRead],
)
def cancel_publish_plan(
    plan_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan_id)
    if plan.status not in {"draft", "approved", "queued", "failed"}:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Plan cannot be cancelled",
            "This publish plan has already reached a final state.",
        )
    plan.status = "cancelled"
    plan.version += 1
    db.commit()
    return DataResponse(
        data=PublishPlanRead.model_validate(plan),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-plans/{plan_id}/publish",
    response_model=DataResponse[PublishPackage],
)
def build_publish_package(
    plan_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan_id)
    if plan.status not in {"approved", "queued"}:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Plan is not approved",
            "Approve the plan before generating its publishing package.",
        )
    script = db.scalar(
        select(ScriptVersion)
        .where(
            ScriptVersion.workspace_id == context.workspace.id,
            ScriptVersion.content_project_id == plan.content_project_id,
            ScriptVersion.deleted_at.is_(None),
        )
        .order_by(ScriptVersion.version_no.desc())
        .limit(1)
    )
    if script is None:
        raise AppError(
            409,
            "PUBLISH_PACKAGE_INCOMPLETE",
            "Script is missing",
            "The publishing package requires a script.",
        )
    assets = db.scalars(
        select(Asset).where(
            Asset.workspace_id == context.workspace.id,
            Asset.content_project_id == plan.content_project_id,
            Asset.deleted_at.is_(None),
        )
    ).all()
    if plan.status == "approved":
        plan.status = "queued"
        plan.version += 1
        db.commit()
    return DataResponse(
        data=PublishPackage(
            plan_id=plan.id,
            plan_version=plan.version,
            project_id=plan.content_project_id,
            channel_id=plan.owned_channel_id,
            scheduled_at=plan.scheduled_at,
            payload=plan.publish_payload,
            latest_script=ScriptVersionRead.model_validate(script),
            assets=[
                {
                    "id": str(asset.id),
                    "asset_type": asset.asset_type,
                    "storage_key": asset.storage_key,
                    "mime_type": asset.mime_type,
                    "rights_note": asset.rights_note,
                }
                for asset in assets
            ],
            publishing_mode="manual",
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-plans/{plan_id}/mark-published",
    response_model=DataResponse[PublishRecordRead],
    status_code=status.HTTP_201_CREATED,
)
def mark_published(
    plan_id: uuid.UUID,
    body: MarkPublishedRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    plan = _get_plan(db, workspace_id=context.workspace.id, plan_id=plan_id)
    if plan.version != body.version:
        raise _plan_version_conflict()
    if plan.status not in {"approved", "queued"}:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Plan cannot be marked published",
            "Only approved manual plans can be marked as published.",
        )
    parsed = urlsplit(body.published_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid published URL",
            "The published URL must be an HTTPS public URL without credentials.",
        )
    existing = db.scalar(select(PublishRecord).where(PublishRecord.publish_plan_id == plan.id))
    if existing is not None:
        return DataResponse(
            data=PublishRecordRead.model_validate(existing),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
    record = PublishRecord(
        workspace_id=context.workspace.id,
        publish_plan_id=plan.id,
        platform_content_id=body.platform_content_id,
        published_url=body.published_url,
        published_at=body.published_at,
        result_payload={"matched_publish_package": body.matched_publish_package},
        created_by=context.membership.user_id,
    )
    db.add(record)
    plan.status = "published"
    plan.version += 1
    project = db.get(ContentProject, plan.content_project_id)
    if project is not None:
        project.status = "published"
        project.version += 1
    db.commit()
    return DataResponse(
        data=PublishRecordRead.model_validate(record),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/publish-records/{record_id}",
    response_model=DataResponse[PublishRecordRead],
)
def get_publish_record(
    record_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    record = _get_record(db, workspace_id=context.workspace.id, record_id=record_id)
    return DataResponse(
        data=PublishRecordRead.model_validate(record),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/publish-records/{record_id}/reviews",
    response_model=DataResponse[list[ReviewInsightRead]],
)
def list_reviews(
    record_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    _get_record(db, workspace_id=context.workspace.id, record_id=record_id)
    reviews = db.scalars(
        select(ReviewInsight)
        .where(
            ReviewInsight.workspace_id == context.workspace.id,
            ReviewInsight.publish_record_id == record_id,
        )
        .order_by(ReviewInsight.created_at.desc())
    ).all()
    return DataResponse(
        data=[ReviewInsightRead.model_validate(item) for item in reviews],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/publish-records/{record_id}/reviews",
    response_model=DataResponse[ReviewInsightRead],
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    record_id: uuid.UUID,
    body: ReviewCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    record = _get_record(db, workspace_id=context.workspace.id, record_id=record_id)
    review = ReviewInsight(
        workspace_id=context.workspace.id,
        publish_record_id=record.id,
        review_window=body.review_window,
        metrics=body.metrics,
        analysis=body.analysis,
        next_actions=body.next_actions,
        created_by=context.membership.user_id,
    )
    db.add(review)
    plan = db.get(PublishPlan, record.publish_plan_id)
    project = db.get(ContentProject, plan.content_project_id) if plan is not None else None
    if project is not None and project.status == "published":
        project.status = "reviewing"
        project.version += 1
    db.commit()
    return DataResponse(
        data=ReviewInsightRead.model_validate(review),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
