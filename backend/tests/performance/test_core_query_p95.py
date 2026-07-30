import math
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import Settings
from app.db.models import (
    ExternalContent,
    User,
    Workspace,
    WorkspaceInspiration,
)
from app.main import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PERFORMANCE") != "1",
    reason="requires an explicit PostgreSQL performance environment",
)


def _p95_ms(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[math.ceil(len(ordered) * 0.95) - 1]


def test_core_inspiration_queries_stay_below_500ms_at_1000_rows():
    database_url = os.environ["DATABASE_URL"]
    settings = Settings(
        app_env="test",
        auth_mode="development",
        database_url=database_url,
        metrics_enabled=False,
    )
    application = create_app(settings)
    subject = f"performance-{uuid.uuid4()}"
    auth = {"Authorization": f"Bearer dev:{subject}"}
    workspace_id = None
    try:
        with TestClient(application) as client:
            workspace = client.post(
                "/api/v1/workspaces",
                headers=auth,
                json={"name": "Performance fixture", "timezone": "UTC"},
            ).json()["data"]
            workspace_id = uuid.UUID(workspace["id"])
            now = datetime.now(timezone.utc)
            with application.state.database.session_factory() as db:
                contents = [
                    ExternalContent(
                        workspace_id=workspace_id,
                        platform="xiaohongshu",
                        external_id=f"performance-{index}",
                        canonical_url=(f"https://www.xiaohongshu.com/explore/performance-{index}"),
                        content_type="video",
                        title=f"Performance inspiration {index}",
                        body_text=f"Searchable benchmark body {index}",
                        published_at=now - timedelta(minutes=index),
                        author_snapshot={},
                        media_manifest=[],
                        detail_status="detail",
                    )
                    for index in range(1000)
                ]
                db.add_all(contents)
                db.flush()
                inspirations = [
                    WorkspaceInspiration(
                        workspace_id=workspace_id,
                        external_content_id=content.id,
                        status="inbox",
                        source="performance_fixture",
                    )
                    for content in contents
                ]
                db.add_all(inspirations)
                db.commit()
                detail_id = inspirations[500].id

            headers = {**auth, "X-Workspace-Id": str(workspace_id)}
            for _ in range(5):
                assert (
                    client.get(
                        "/api/v1/inspirations?limit=20",
                        headers=headers,
                    ).status_code
                    == 200
                )

            list_samples = []
            detail_samples = []
            for _ in range(30):
                started = time.perf_counter()
                response = client.get(
                    "/api/v1/inspirations?limit=20",
                    headers=headers,
                )
                list_samples.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200

                started = time.perf_counter()
                response = client.get(
                    f"/api/v1/inspirations/{detail_id}",
                    headers=headers,
                )
                detail_samples.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200

            list_p95 = _p95_ms(list_samples)
            detail_p95 = _p95_ms(detail_samples)
            print(
                {
                    "rows": 1000,
                    "samples": 30,
                    "list_p95_ms": round(list_p95, 2),
                    "detail_p95_ms": round(detail_p95, 2),
                }
            )
            assert list_p95 < 500
            assert detail_p95 < 500
    finally:
        if workspace_id is not None:
            with application.state.database.session_factory() as db:
                db.execute(delete(Workspace).where(Workspace.id == workspace_id))
                user = db.scalar(select(User).where(User.external_subject == subject))
                if user is not None:
                    db.delete(user)
                db.commit()
        application.state.database.dispose()
