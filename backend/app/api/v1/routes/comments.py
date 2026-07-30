import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.db.models import CommentSample
from app.jobs.service import create_job
from app.modules.analysis.service import inspiration_content
from app.modules.comments.schemas import CommentFetchRequest, CommentSampleRead
from app.schemas.common import DataResponse, JobAccepted, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["comments"])


@router.post(
    "/inspirations/{inspiration_id}/fetch-comments",
    response_model=DataResponse[JobAccepted],
    status_code=202,
)
def fetch_comments(
    inspiration_id: uuid.UUID,
    body: CommentFetchRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    content = inspiration_content(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="COMMENT_FETCH",
        dedupe_key=f"comments:{content.id}",
        payload={
            "external_content_id": str(content.id),
            "max_pages": body.max_pages,
            "sort_strategy": body.sort_strategy,
        },
        priority=55,
    )
    db.commit()
    return DataResponse(
        data=JobAccepted(job_id=job.id, status=job.status),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/inspirations/{inspiration_id}/comments",
    response_model=DataResponse[list[CommentSampleRead]],
)
def list_comments(
    inspiration_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    content = inspiration_content(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    comments = db.scalars(
        select(CommentSample)
        .where(
            CommentSample.workspace_id == context.workspace.id,
            CommentSample.external_content_id == content.id,
        )
        .order_by(
            CommentSample.like_count.desc().nullslast(),
            CommentSample.captured_at.desc(),
        )
        .limit(limit)
    ).all()
    return DataResponse(
        data=[CommentSampleRead.model_validate(comment) for comment in comments],
        meta=ResponseMeta(request_id=request.state.request_id),
    )
