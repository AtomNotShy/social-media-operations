import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.errors import AppError
from app.db.models import AnalysisRun, ReusablePattern
from app.modules.patterns.schemas import PatternCreate, PatternRead, PatternUpdate
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/patterns", tags=["patterns"])


def _get_pattern(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    pattern_id: uuid.UUID,
) -> ReusablePattern:
    pattern = db.scalar(
        select(ReusablePattern).where(
            ReusablePattern.workspace_id == workspace_id,
            ReusablePattern.id == pattern_id,
        )
    )
    if pattern is None:
        raise AppError(404, "NOT_FOUND", "Pattern not found", "Pattern not found.")
    return pattern


@router.get("", response_model=DataResponse[list[PatternRead]])
def list_patterns(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(ReusablePattern).where(ReusablePattern.workspace_id == context.workspace.id)
    if status_filter:
        query = query.where(ReusablePattern.status == status_filter)
    patterns = db.scalars(
        query.order_by(ReusablePattern.updated_at.desc(), ReusablePattern.id.desc())
    ).all()
    return DataResponse(
        data=[PatternRead.model_validate(item) for item in patterns],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "",
    response_model=DataResponse[PatternRead],
    status_code=status.HTTP_201_CREATED,
)
def create_pattern(
    body: PatternCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    pattern = ReusablePattern(
        workspace_id=context.workspace.id,
        name=body.name,
        description=body.description,
        pattern_type=body.pattern_type,
        applicable_channels=[str(item) for item in body.applicable_channels],
        source_content_ids=[str(item) for item in body.source_content_ids],
        evidence=body.evidence,
        created_by=context.membership.user_id,
    )
    db.add(pattern)
    db.commit()
    return DataResponse(
        data=PatternRead.model_validate(pattern),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{pattern_id}", response_model=DataResponse[PatternRead])
def get_pattern(
    pattern_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    pattern = _get_pattern(
        db,
        workspace_id=context.workspace.id,
        pattern_id=pattern_id,
    )
    return DataResponse(
        data=PatternRead.model_validate(pattern),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch("/{pattern_id}", response_model=DataResponse[PatternRead])
def update_pattern(
    pattern_id: uuid.UUID,
    body: PatternUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    pattern = _get_pattern(
        db,
        workspace_id=context.workspace.id,
        pattern_id=pattern_id,
    )
    changes = body.model_dump(exclude_unset=True)
    for field in ("applicable_channels", "source_content_ids"):
        if field in changes and changes[field] is not None:
            changes[field] = [str(item) for item in changes[field]]
    for name, value in changes.items():
        setattr(pattern, name, value)
    db.commit()
    return DataResponse(
        data=PatternRead.model_validate(pattern),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pattern(
    pattern_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> Response:
    pattern = _get_pattern(
        db,
        workspace_id=context.workspace.id,
        pattern_id=pattern_id,
    )
    if pattern.status != "draft":
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Pattern cannot be deleted",
            "Only draft patterns can be deleted; retire validated patterns instead.",
        )
    db.delete(pattern)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/from-analysis/{analysis_id}",
    response_model=DataResponse[list[PatternRead]],
)
def create_patterns_from_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    analysis = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.workspace_id == context.workspace.id,
            AnalysisRun.id == analysis_id,
            AnalysisRun.status == "succeeded",
        )
    )
    if analysis is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Analysis not found",
            "A successful analysis was not found.",
        )
    candidates = (analysis.result or {}).get("reusable_patterns")
    if not isinstance(candidates, list) or not candidates:
        raise AppError(
            409,
            "PATTERN_SOURCE_EMPTY",
            "No reusable patterns found",
            "The analysis did not produce reusable patterns.",
        )
    analysis_id_text = str(analysis.id)
    existing_patterns = db.scalars(
        select(ReusablePattern).where(
            ReusablePattern.workspace_id == context.workspace.id
        )
    ).all()
    existing_names = {
        pattern.name.strip()
        for pattern in existing_patterns
        if (pattern.evidence or {}).get("analysis_id") == analysis_id_text
    }

    candidates = [
        value.strip()
        for value in candidates[:20]
        if isinstance(value, str) and value.strip()
    ]
    unique_candidates = list(dict.fromkeys(candidates))
    patterns = []
    for value in unique_candidates:
        name = value[:255]
        if name in existing_names:
            continue
        pattern = ReusablePattern(
            workspace_id=context.workspace.id,
            name=name,
            description=value,
            pattern_type="structure",
            source_content_ids=[str(analysis.external_content_id)],
            evidence={
                "analysis_id": analysis_id_text,
                "evidence_refs": analysis.evidence_refs,
            },
            created_by=context.membership.user_id,
        )
        db.add(pattern)
        patterns.append(pattern)
        existing_names.add(name)
    if patterns:
        db.commit()
        response.status_code = status.HTTP_201_CREATED
        return DataResponse(
            data=[PatternRead.model_validate(item) for item in patterns],
            meta=ResponseMeta(request_id=request.state.request_id),
        )
    if not unique_candidates:
        raise AppError(
            409,
            "PATTERN_SOURCE_EMPTY",
            "No reusable patterns found",
            "The analysis patterns were empty or invalid.",
        )
    return DataResponse(
        data=[],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


def _transition_pattern(
    pattern_id: uuid.UUID,
    target: str,
    request: Request,
    context: WorkspaceContext,
    db: Session,
) -> DataResponse:
    pattern = _get_pattern(
        db,
        workspace_id=context.workspace.id,
        pattern_id=pattern_id,
    )
    pattern.status = target
    db.commit()
    return DataResponse(
        data=PatternRead.model_validate(pattern),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/{pattern_id}/validate", response_model=DataResponse[PatternRead])
def validate_pattern(
    pattern_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    return _transition_pattern(pattern_id, "validated", request, context, db)


@router.post("/{pattern_id}/retire", response_model=DataResponse[PatternRead])
def retire_pattern(
    pattern_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    return _transition_pattern(pattern_id, "retired", request, context, db)
