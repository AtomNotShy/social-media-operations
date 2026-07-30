import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import (
    AttributionEvent,
    ContentProject,
    Experiment,
    ExperimentAssignment,
    OwnedChannel,
    PublishPlan,
    PublishRecord,
    SavedView,
)
from app.modules.experiments.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AttributionEventCreate,
    AttributionEventRead,
    ExperimentCreate,
    ExperimentRead,
    ExperimentResultsRead,
    ExperimentUpdate,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
    VariantMetricResult,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["experiments"])


def _get_saved_view(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    view_id: uuid.UUID,
) -> SavedView:
    view = db.scalar(
        select(SavedView).where(
            SavedView.workspace_id == workspace_id,
            SavedView.id == view_id,
        )
    )
    if view is None:
        raise AppError(404, "NOT_FOUND", "Saved view not found", "Saved view not found.")
    return view


def _can_manage_view(context: WorkspaceContext, view: SavedView) -> bool:
    return view.user_id == context.membership.user_id or context.membership.role == "owner"


def _get_experiment(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    experiment_id: uuid.UUID,
) -> Experiment:
    experiment = db.scalar(
        select(Experiment).where(
            Experiment.workspace_id == workspace_id,
            Experiment.id == experiment_id,
        )
    )
    if experiment is None:
        raise AppError(404, "NOT_FOUND", "Experiment not found", "Experiment not found.")
    return experiment


def _event_read(event: AttributionEvent) -> AttributionEventRead:
    return AttributionEventRead(
        id=event.id,
        experiment_id=event.experiment_id,
        assignment_id=event.assignment_id,
        publish_record_id=event.publish_record_id,
        event_type=event.event_type,
        metric_name=event.metric_name,
        value=event.value,
        occurred_at=event.occurred_at,
        source=event.source,
        source_ref=event.source_ref,
        idempotency_key=event.idempotency_key,
        metadata=event.metadata_json,
        created_at=event.created_at,
    )


@router.get("/saved-views", response_model=DataResponse[list[SavedViewRead]])
def list_saved_views(
    request: Request,
    entity_type: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    statement = select(SavedView).where(
        SavedView.workspace_id == context.workspace.id,
        or_(
            SavedView.user_id == context.membership.user_id,
            SavedView.is_shared.is_(True),
        ),
    )
    if entity_type:
        statement = statement.where(SavedView.entity_type == entity_type)
    views = db.scalars(statement.order_by(SavedView.entity_type, SavedView.name)).all()
    return DataResponse(
        data=[SavedViewRead.model_validate(item) for item in views],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/saved-views",
    response_model=DataResponse[SavedViewRead],
    status_code=status.HTTP_201_CREATED,
)
def create_saved_view(
    body: SavedViewCreate,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    view = SavedView(
        workspace_id=context.workspace.id,
        user_id=context.membership.user_id,
        **body.model_dump(),
    )
    try:
        db.add(view)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Saved view already exists",
            "A saved view with this name already exists for this entity type.",
        ) from exc
    return DataResponse(
        data=SavedViewRead.model_validate(view),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/saved-views/{view_id}", response_model=DataResponse[SavedViewRead])
def update_saved_view(
    view_id: uuid.UUID,
    body: SavedViewUpdate,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    view = _get_saved_view(db, workspace_id=context.workspace.id, view_id=view_id)
    if not _can_manage_view(context, view):
        raise AppError(403, "FORBIDDEN", "Access denied", "This saved view is read-only.")
    values = body.model_dump(exclude={"version"}, exclude_unset=True)
    result = db.execute(
        update(SavedView)
        .where(SavedView.id == view.id, SavedView.version == body.version)
        .values(**values, version=SavedView.version + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Saved view was changed",
            "Reload the saved view before updating it.",
        )
    db.commit()
    view = _get_saved_view(db, workspace_id=context.workspace.id, view_id=view_id)
    return DataResponse(
        data=SavedViewRead.model_validate(view),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete("/saved-views/{view_id}", status_code=204)
def delete_saved_view(
    view_id: uuid.UUID,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> None:
    view = _get_saved_view(db, workspace_id=context.workspace.id, view_id=view_id)
    if not _can_manage_view(context, view):
        raise AppError(403, "FORBIDDEN", "Access denied", "This saved view is read-only.")
    db.delete(view)
    db.commit()


@router.get("/experiments", response_model=DataResponse[list[ExperimentRead]])
def list_experiments(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    statement = select(Experiment).where(Experiment.workspace_id == context.workspace.id)
    if status_filter:
        statement = statement.where(Experiment.status == status_filter)
    experiments = db.scalars(statement.order_by(Experiment.created_at.desc())).all()
    return DataResponse(
        data=[ExperimentRead.model_validate(item) for item in experiments],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/experiments",
    response_model=DataResponse[ExperimentRead],
    status_code=status.HTTP_201_CREATED,
)
def create_experiment(
    body: ExperimentCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    if body.owned_channel_id is not None:
        channel = db.scalar(
            select(OwnedChannel).where(
                OwnedChannel.workspace_id == context.workspace.id,
                OwnedChannel.id == body.owned_channel_id,
                OwnedChannel.active.is_(True),
            )
        )
        if channel is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Owned channel not found",
                "The experiment channel must belong to the current workspace.",
            )
    experiment = Experiment(
        workspace_id=context.workspace.id,
        owned_channel_id=body.owned_channel_id,
        name=body.name,
        hypothesis=body.hypothesis,
        primary_metric=body.primary_metric,
        variants=[item.model_dump() for item in body.variants],
        created_by=context.membership.user_id,
    )
    db.add(experiment)
    db.commit()
    return DataResponse(
        data=ExperimentRead.model_validate(experiment),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/experiments/{experiment_id}", response_model=DataResponse[ExperimentRead])
def get_experiment(
    experiment_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    experiment = _get_experiment(
        db,
        workspace_id=context.workspace.id,
        experiment_id=experiment_id,
    )
    return DataResponse(
        data=ExperimentRead.model_validate(experiment),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/experiments/{experiment_id}", response_model=DataResponse[ExperimentRead])
def update_experiment(
    experiment_id: uuid.UUID,
    body: ExperimentUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    experiment = _get_experiment(
        db,
        workspace_id=context.workspace.id,
        experiment_id=experiment_id,
    )
    values = body.model_dump(exclude={"version", "status"}, exclude_unset=True)
    next_status = body.status
    if experiment.status != "draft" and values:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Experiment definition is frozen",
            "Hypothesis and metric fields cannot change after the experiment starts.",
        )
    allowed = {
        "draft": {"draft", "running", "cancelled"},
        "running": {"running", "completed", "cancelled"},
        "completed": {"completed"},
        "cancelled": {"cancelled"},
    }
    if next_status is not None and next_status not in allowed.get(experiment.status, set()):
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Invalid experiment transition",
            f"Experiment cannot transition from {experiment.status} to {next_status}.",
        )
    if next_status is not None:
        values["status"] = next_status
        if experiment.status == "draft" and next_status == "running":
            values["started_at"] = datetime.now(timezone.utc)
        if next_status in {"completed", "cancelled"} and experiment.status != next_status:
            values["ended_at"] = datetime.now(timezone.utc)
    result = db.execute(
        update(Experiment)
        .where(
            Experiment.id == experiment.id,
            Experiment.workspace_id == context.workspace.id,
            Experiment.version == body.version,
        )
        .values(**values, version=Experiment.version + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Experiment was changed",
            "Reload the experiment before updating it.",
        )
    db.commit()
    experiment = _get_experiment(
        db,
        workspace_id=context.workspace.id,
        experiment_id=experiment_id,
    )
    return DataResponse(
        data=ExperimentRead.model_validate(experiment),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/experiments/{experiment_id}/assignments",
    response_model=DataResponse[list[AssignmentRead]],
)
def list_assignments(
    experiment_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    _get_experiment(db, workspace_id=context.workspace.id, experiment_id=experiment_id)
    assignments = db.scalars(
        select(ExperimentAssignment)
        .where(
            ExperimentAssignment.workspace_id == context.workspace.id,
            ExperimentAssignment.experiment_id == experiment_id,
        )
        .order_by(ExperimentAssignment.created_at, ExperimentAssignment.id)
    ).all()
    return DataResponse(
        data=[AssignmentRead.model_validate(item) for item in assignments],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/experiments/{experiment_id}/assignments",
    response_model=DataResponse[AssignmentRead],
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    experiment_id: uuid.UUID,
    body: AssignmentCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    experiment = _get_experiment(
        db,
        workspace_id=context.workspace.id,
        experiment_id=experiment_id,
    )
    if experiment.status not in {"draft", "running"}:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Experiment is closed",
            "Assignments can only be created for draft or running experiments.",
        )
    if body.variant_key not in {item["key"] for item in experiment.variants}:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Unknown experiment variant",
            "The assignment variant is not defined by this experiment version.",
        )
    project = db.scalar(
        select(ContentProject).where(
            ContentProject.workspace_id == context.workspace.id,
            ContentProject.id == body.content_project_id,
            ContentProject.deleted_at.is_(None),
        )
    )
    if project is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Content project not found",
            "The assigned project must belong to the current workspace.",
        )
    if experiment.owned_channel_id and project.owned_channel_id != experiment.owned_channel_id:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Experiment channel mismatch",
            "The project channel does not match the experiment channel.",
        )
    assignment = ExperimentAssignment(
        workspace_id=context.workspace.id,
        experiment_id=experiment.id,
        content_project_id=project.id,
        variant_key=body.variant_key,
        assigned_by=context.membership.user_id,
    )
    try:
        db.add(assignment)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "DUPLICATE_RESOURCE",
            "Project is already assigned",
            "A content project can only be assigned once per experiment.",
        ) from exc
    return DataResponse(
        data=AssignmentRead.model_validate(assignment),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/experiments/{experiment_id}/events",
    response_model=DataResponse[AttributionEventRead],
    status_code=status.HTTP_201_CREATED,
)
def create_attribution_event(
    experiment_id: uuid.UUID,
    body: AttributionEventCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    experiment = _get_experiment(
        db,
        workspace_id=context.workspace.id,
        experiment_id=experiment_id,
    )
    if experiment.status != "running":
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            "Experiment is not running",
            "Attribution events are accepted only while the experiment is running.",
        )
    assignment = db.scalar(
        select(ExperimentAssignment).where(
            ExperimentAssignment.workspace_id == context.workspace.id,
            ExperimentAssignment.experiment_id == experiment.id,
            ExperimentAssignment.id == body.assignment_id,
        )
    )
    if assignment is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Assignment not found",
            "The attribution assignment does not belong to this experiment.",
        )
    if body.publish_record_id is not None:
        matching_record = db.scalar(
            select(PublishRecord)
            .join(PublishPlan, PublishPlan.id == PublishRecord.publish_plan_id)
            .where(
                PublishRecord.workspace_id == context.workspace.id,
                PublishRecord.id == body.publish_record_id,
                PublishPlan.content_project_id == assignment.content_project_id,
            )
        )
        if matching_record is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Publish record mismatch",
                "The publish record must belong to the assigned content project.",
            )
    existing = db.scalar(
        select(AttributionEvent).where(
            AttributionEvent.workspace_id == context.workspace.id,
            AttributionEvent.idempotency_key == body.idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.experiment_id != experiment.id
            or existing.assignment_id != assignment.id
            or existing.metric_name != body.metric_name
            or existing.value != body.value
            or existing.source_ref != body.source_ref
        ):
            raise AppError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency key was reused",
                "The idempotency key is already bound to a different event.",
            )
        return DataResponse(
            data=_event_read(existing),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
    event = AttributionEvent(
        workspace_id=context.workspace.id,
        experiment_id=experiment.id,
        assignment_id=assignment.id,
        publish_record_id=body.publish_record_id,
        event_type=body.event_type,
        metric_name=body.metric_name,
        value=body.value,
        occurred_at=body.occurred_at,
        source=body.source,
        source_ref=body.source_ref,
        idempotency_key=body.idempotency_key,
        metadata_json=body.metadata,
    )
    db.add(event)
    db.commit()
    return DataResponse(
        data=_event_read(event),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/experiments/{experiment_id}/results",
    response_model=DataResponse[ExperimentResultsRead],
)
def get_experiment_results(
    experiment_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    experiment = _get_experiment(
        db,
        workspace_id=context.workspace.id,
        experiment_id=experiment_id,
    )
    assignments = db.scalars(
        select(ExperimentAssignment).where(
            ExperimentAssignment.workspace_id == context.workspace.id,
            ExperimentAssignment.experiment_id == experiment.id,
        )
    ).all()
    events = db.scalars(
        select(AttributionEvent)
        .where(
            AttributionEvent.workspace_id == context.workspace.id,
            AttributionEvent.experiment_id == experiment.id,
            AttributionEvent.metric_name == experiment.primary_metric,
        )
        .order_by(AttributionEvent.occurred_at, AttributionEvent.id)
    ).all()
    assignment_by_id = {item.id: item for item in assignments}
    data_by_variant = {
        item["key"]: {
            "assignment_ids": set(),
            "events": [],
            "total": Decimal("0"),
            "source_refs": set(),
        }
        for item in experiment.variants
    }
    for assignment in assignments:
        data_by_variant[assignment.variant_key]["assignment_ids"].add(assignment.id)
    for event in events:
        assignment = assignment_by_id.get(event.assignment_id)
        if assignment is None:
            continue
        bucket = data_by_variant[assignment.variant_key]
        bucket["events"].append(event.id)
        bucket["total"] += event.value
        bucket["source_refs"].add(event.source_ref)
    variants = [
        VariantMetricResult(
            variant_key=item["key"],
            assignment_count=len(data_by_variant[item["key"]]["assignment_ids"]),
            event_count=len(data_by_variant[item["key"]]["events"]),
            total_value=data_by_variant[item["key"]]["total"],
            evidence_event_ids=data_by_variant[item["key"]]["events"],
            source_refs=sorted(data_by_variant[item["key"]]["source_refs"]),
        )
        for item in experiment.variants
    ]
    return DataResponse(
        data=ExperimentResultsRead(
            experiment_id=experiment.id,
            experiment_version=experiment.version,
            primary_metric=experiment.primary_metric,
            generated_at=datetime.now(timezone.utc),
            variants=variants,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
