from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import WorkspaceContext, get_db, get_workspace_context
from app.db.models import (
    ContentProject,
    ExternalContent,
    ReusablePattern,
    Topic,
    WorkspaceInspiration,
)
from app.modules.inspirations.service import latest_score_is_qualified_clause
from app.modules.search.schemas import SearchEntityType, UnifiedSearchResult
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def _matched_fields(query: str, fields: dict[str, str | None]) -> list[str]:
    needle = query.casefold()
    return [
        name
        for name, value in fields.items()
        if isinstance(value, str) and needle in value.casefold()
    ]


def _snippet(query: str, values: list[str | None], *, max_length: int = 220) -> str | None:
    text = next(
        (
            value.strip()
            for value in values
            if isinstance(value, str) and query.casefold() in value.casefold()
        ),
        None,
    )
    if text is None:
        return None
    index = text.casefold().find(query.casefold())
    start = max(0, index - 70)
    end = min(len(text), start + max_length)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


@router.get("", response_model=DataResponse[list[UnifiedSearchResult]])
def unified_search(
    request: Request,
    q: str = Query(min_length=1, max_length=100),
    entity_types: list[Literal["inspiration", "pattern", "topic", "content_project"]] = Query(
        default=["inspiration", "pattern", "topic", "content_project"],
        alias="type",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query_text = q.strip()
    pattern = f"%{query_text}%"
    selected_types: set[SearchEntityType] = set(entity_types)
    results: list[UnifiedSearchResult] = []

    if "inspiration" in selected_types:
        rows = db.execute(
            select(WorkspaceInspiration, ExternalContent)
            .join(
                ExternalContent,
                ExternalContent.id == WorkspaceInspiration.external_content_id,
            )
            .where(
                WorkspaceInspiration.workspace_id == context.workspace.id,
                ExternalContent.workspace_id == context.workspace.id,
                or_(
                    WorkspaceInspiration.source != "tracked_profile",
                    latest_score_is_qualified_clause(
                        workspace_id=context.workspace.id,
                        external_content_id=ExternalContent.id,
                    ),
                ),
                or_(
                    ExternalContent.title.ilike(pattern),
                    ExternalContent.body_text.ilike(pattern),
                    WorkspaceInspiration.notes.ilike(pattern),
                ),
            )
            .limit(limit)
        ).all()
        for inspiration, content in rows:
            fields = {
                "title": content.title,
                "body_text": content.body_text,
                "notes": inspiration.notes,
            }
            results.append(
                UnifiedSearchResult(
                    entity_type="inspiration",
                    entity_id=inspiration.id,
                    title=content.title or content.body_text or content.external_id,
                    snippet=_snippet(
                        query_text,
                        [content.title, content.body_text, inspiration.notes],
                    ),
                    matched_fields=_matched_fields(query_text, fields),
                    source_ref=f"/api/v1/inspirations/{inspiration.id}",
                    updated_at=inspiration.updated_at,
                )
            )

    if "pattern" in selected_types:
        rows = db.scalars(
            select(ReusablePattern)
            .where(
                ReusablePattern.workspace_id == context.workspace.id,
                or_(
                    ReusablePattern.name.ilike(pattern),
                    ReusablePattern.description.ilike(pattern),
                ),
            )
            .limit(limit)
        ).all()
        for item in rows:
            results.append(
                UnifiedSearchResult(
                    entity_type="pattern",
                    entity_id=item.id,
                    title=item.name,
                    snippet=_snippet(query_text, [item.name, item.description]),
                    matched_fields=_matched_fields(
                        query_text,
                        {"name": item.name, "description": item.description},
                    ),
                    source_ref=f"/api/v1/patterns/{item.id}",
                    updated_at=item.updated_at,
                )
            )

    if "topic" in selected_types:
        rows = db.scalars(
            select(Topic)
            .where(
                Topic.workspace_id == context.workspace.id,
                Topic.deleted_at.is_(None),
                or_(
                    Topic.title.ilike(pattern),
                    Topic.audience_problem.ilike(pattern),
                    Topic.angle.ilike(pattern),
                    Topic.hook.ilike(pattern),
                ),
            )
            .limit(limit)
        ).all()
        for item in rows:
            fields = {
                "title": item.title,
                "audience_problem": item.audience_problem,
                "angle": item.angle,
                "hook": item.hook,
            }
            results.append(
                UnifiedSearchResult(
                    entity_type="topic",
                    entity_id=item.id,
                    title=item.title,
                    snippet=_snippet(query_text, list(fields.values())),
                    matched_fields=_matched_fields(query_text, fields),
                    source_ref=f"/api/v1/topics/{item.id}",
                    updated_at=item.updated_at,
                )
            )

    if "content_project" in selected_types:
        rows = db.scalars(
            select(ContentProject)
            .where(
                ContentProject.workspace_id == context.workspace.id,
                ContentProject.deleted_at.is_(None),
                ContentProject.title.ilike(pattern),
            )
            .limit(limit)
        ).all()
        for item in rows:
            results.append(
                UnifiedSearchResult(
                    entity_type="content_project",
                    entity_id=item.id,
                    title=item.title,
                    snippet=_snippet(query_text, [item.title]),
                    matched_fields=["title"],
                    source_ref=f"/api/v1/content-projects/{item.id}",
                    updated_at=item.updated_at,
                )
            )

    results.sort(key=lambda item: (item.updated_at, str(item.entity_id)), reverse=True)
    return DataResponse(
        data=results[:limit],
        meta=ResponseMeta(request_id=request.state.request_id),
    )
