"""Resolve topic evidence references into generation source material.

Phase-0 context pack: every ``content:`` / ``inspiration:`` reference on a
topic must resolve to a real external content row in the workspace. A dangling
reference fails the request explicitly instead of silently generating without
the cited source.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import ExternalContent, WorkspaceInspiration

MAX_EVIDENCE_BODY_CHARS = 20_000
MAX_EVIDENCE_UNITS = 10
EVIDENCE_CONTEXT_VERSION = "evidence-v1"


def _trim(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[:limit]}\n[truncated]"


def _content_evidence_refs(evidence_refs: list) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for ref in evidence_refs or []:
        raw = str(ref)
        kind, _, value = raw.partition(":")
        if kind in {"content", "inspiration"} and value:
            refs.append((kind, value))
    return refs


def _resolve_content(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    kind: str,
    value: str,
) -> ExternalContent | None:
    try:
        entity_id = uuid.UUID(value)
    except (TypeError, ValueError):
        raise AppError(
            409,
            "EVIDENCE_UNAVAILABLE",
            "Topic evidence reference is invalid",
            f"Evidence reference {kind}:{value} cannot be resolved.",
        ) from None
    if kind == "content":
        return db.scalar(
            select(ExternalContent).where(
                ExternalContent.workspace_id == workspace_id,
                ExternalContent.id == entity_id,
            )
        )
    row = db.execute(
        select(ExternalContent)
        .join(
            WorkspaceInspiration,
            WorkspaceInspiration.external_content_id == ExternalContent.id,
        )
        .where(
            WorkspaceInspiration.workspace_id == workspace_id,
            WorkspaceInspiration.id == entity_id,
            ExternalContent.workspace_id == workspace_id,
        )
    ).one_or_none()
    return row[0] if row is not None else None


def resolve_topic_evidence(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    evidence_refs: list,
) -> list[dict]:
    """Resolve content-backed topic evidence into source material units.

    Returns an empty list when the topic carries no content-bearing refs.
    Raises ``EVIDENCE_UNAVAILABLE`` when any content-bearing ref cannot be
    resolved, so a run is never queued with a broken evidence contract.
    Units are deduplicated by the underlying external content id.
    """
    pending = _content_evidence_refs(evidence_refs)
    if not pending:
        return []
    units_by_content: dict[uuid.UUID, dict] = {}
    for kind, value in pending:
        content = _resolve_content(
            db,
            workspace_id=workspace_id,
            kind=kind,
            value=value,
        )
        if content is None:
            raise AppError(
                409,
                "EVIDENCE_UNAVAILABLE",
                "Topic evidence is not available",
                f"Evidence reference {kind}:{value} no longer resolves to source content.",
            )
        if content.id in units_by_content:
            continue
        units_by_content[content.id] = {
            "ref": f"content:{content.id}",
            "platform": content.platform,
            "content_type": content.content_type,
            "title": content.title,
            "body": _trim(content.body_text, MAX_EVIDENCE_BODY_CHARS),
            "canonical_url": content.canonical_url,
            "published_at": (
                content.published_at.isoformat()
                if content.published_at is not None
                else None
            ),
            "author": content.author_snapshot or None,
        }
    units = list(units_by_content.values())
    return units[:MAX_EVIDENCE_UNITS]
