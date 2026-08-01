from uuid import UUID

from sqlalchemy import func, select

from app.db.models import ExternalContent, WorkspaceInspiration
from app.modules.inspirations.service import (
    ensure_workspace_inspiration,
    promote_scored_content,
)


def test_score_promotion_threshold_is_idempotent_after_later_qualification(app, workspace):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="later-qualified",
            canonical_url="https://www.xiaohongshu.com/explore/later-qualified",
            content_type="image_text",
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.commit()
        content_id = content.id

        assert (
            promote_scored_content(
                db,
                workspace_id=workspace_id,
                external_content_id=content_id,
                grade="insufficient",
                source="tracked_profile",
            )
            is None
        )
        assert db.scalar(select(func.count()).select_from(WorkspaceInspiration)) == 0

        promoted = promote_scored_content(
            db,
            workspace_id=workspace_id,
            external_content_id=content_id,
            grade="t1",
            source="tracked_profile",
        )
        db.commit()
        assert promoted is not None
        again = promote_scored_content(
            db,
            workspace_id=workspace_id,
            external_content_id=content_id,
            grade="t2",
            source="tracked_profile",
        )
        assert again is not None
        assert again.id == promoted.id
        assert db.scalar(select(func.count()).select_from(WorkspaceInspiration)) == 1


def test_explicit_discovery_import_overrides_legacy_tracked_profile_source(app, workspace):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="explicit-discovery-import",
            canonical_url="https://www.xiaohongshu.com/explore/explicit-discovery-import",
            content_type="image_text",
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        legacy = WorkspaceInspiration(
            workspace_id=workspace_id,
            external_content_id=content.id,
            source="tracked_profile",
        )
        db.add(legacy)
        db.commit()

        imported = ensure_workspace_inspiration(
            db,
            workspace_id=workspace_id,
            external_content_id=content.id,
            source="discovery_search",
        )
        db.commit()

        assert imported.id == legacy.id
        assert imported.source == "discovery_search"
