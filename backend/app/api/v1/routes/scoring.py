import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import ContentScore, ScoringPolicy, WorkspaceInspiration
from app.modules.scoring.schemas import (
    ContentScoreRead,
    ScoringPolicyCreate,
    ScoringPolicyRead,
)
from app.modules.scoring.service import calculate_content_score, validate_scoring_policy
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["scoring"])


def _content_id_for_inspiration(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    inspiration_id: uuid.UUID,
) -> uuid.UUID:
    content_id = db.scalar(
        select(WorkspaceInspiration.external_content_id).where(
            WorkspaceInspiration.workspace_id == workspace_id,
            WorkspaceInspiration.id == inspiration_id,
        )
    )
    if content_id is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Inspiration not found",
            "Inspiration not found.",
        )
    return content_id


@router.get(
    "/inspirations/{inspiration_id}/scores",
    response_model=DataResponse[list[ContentScoreRead]],
)
def list_scores(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    content_id = _content_id_for_inspiration(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    scores = db.scalars(
        select(ContentScore)
        .where(
            ContentScore.workspace_id == context.workspace.id,
            ContentScore.external_content_id == content_id,
        )
        .order_by(ContentScore.calculated_at.desc(), ContentScore.id.desc())
    ).all()
    return DataResponse(
        data=[ContentScoreRead.model_validate(score) for score in scores],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/inspirations/{inspiration_id}/scores/recalculate",
    response_model=DataResponse[ContentScoreRead],
    status_code=status.HTTP_201_CREATED,
)
def recalculate_score(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    content_id = _content_id_for_inspiration(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    score = calculate_content_score(
        db,
        workspace_id=context.workspace.id,
        content_id=content_id,
    )
    db.commit()
    return DataResponse(
        data=ContentScoreRead.model_validate(score),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/scoring-policies",
    response_model=DataResponse[list[ScoringPolicyRead]],
)
def list_scoring_policies(
    request: Request,
    platform: str | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(ScoringPolicy).where(ScoringPolicy.workspace_id == context.workspace.id)
    if platform:
        query = query.where(ScoringPolicy.platform == platform)
    policies = db.scalars(
        query.order_by(
            ScoringPolicy.platform,
            ScoringPolicy.version.desc(),
        )
    ).all()
    return DataResponse(
        data=[ScoringPolicyRead.model_validate(policy) for policy in policies],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/scoring-policies",
    response_model=DataResponse[ScoringPolicyRead],
    status_code=status.HTTP_201_CREATED,
)
def create_scoring_policy(
    body: ScoringPolicyCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    latest_version = db.scalar(
        select(func.max(ScoringPolicy.version)).where(
            ScoringPolicy.workspace_id == context.workspace.id,
            ScoringPolicy.platform == body.platform,
        )
    )
    policy = ScoringPolicy(
        workspace_id=context.workspace.id,
        platform=body.platform,
        version=(latest_version or 0) + 1,
        core_metric_formula=body.core_metric_formula,
        tier_thresholds=body.tier_thresholds,
        grade_thresholds=body.grade_thresholds,
        minimum_age_minutes=body.minimum_age_minutes,
        minimum_baseline_count=body.minimum_baseline_count,
        active=False,
    )
    validate_scoring_policy(policy)
    try:
        db.add(policy)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Scoring policy conflict",
            "A concurrent scoring policy version was created. Retry the request.",
        ) from exc
    return DataResponse(
        data=ScoringPolicyRead.model_validate(policy),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/scoring-policies/{policy_id}/activate",
    response_model=DataResponse[ScoringPolicyRead],
)
def activate_scoring_policy(
    policy_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    policy = db.scalar(
        select(ScoringPolicy).where(
            ScoringPolicy.workspace_id == context.workspace.id,
            ScoringPolicy.id == policy_id,
        )
    )
    if policy is None:
        raise AppError(404, "NOT_FOUND", "Scoring policy not found", "Policy not found.")
    validate_scoring_policy(policy)
    db.execute(
        update(ScoringPolicy)
        .where(
            ScoringPolicy.workspace_id == context.workspace.id,
            ScoringPolicy.platform == policy.platform,
            ScoringPolicy.active.is_(True),
            ScoringPolicy.id != policy.id,
        )
        .values(active=False)
    )
    db.flush()
    policy.active = True
    db.commit()
    return DataResponse(
        data=ScoringPolicyRead.model_validate(policy),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
