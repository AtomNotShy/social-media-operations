import asyncio
import json
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.db.models import (
    CommentSample,
    ExternalContent,
    ProviderFetch,
    SyncJob,
    WorkspaceInspiration,
)
from app.jobs.worker import process_one
from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.xiaohongshu import XiaohongshuAppV2Adapter

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture():
    return json.loads((FIXTURES / "xhs_comments_representative.json").read_text(encoding="utf-8"))


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _seed_inspiration(app, workspace):
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=UUID(workspace["id"]),
            platform="xiaohongshu",
            external_id="comment-note",
            canonical_url="https://www.xiaohongshu.com/explore/comment-note",
            content_type="image_text",
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        inspiration = WorkspaceInspiration(
            workspace_id=UUID(workspace["id"]),
            external_content_id=content.id,
            source="test",
        )
        db.add(inspiration)
        db.commit()
        return str(inspiration.id)


def test_representative_comment_fixture_is_normalized():
    page = XiaohongshuAppV2Adapter().parse_comments(_fixture())

    assert page.has_more is False
    assert page.index == 1
    assert len(page.items) == 1
    assert page.items[0].external_id == "comment-fixture-001"
    assert page.items[0].author == {
        "external_id": "commenter-fixture-001",
        "display_name": "示例用户",
    }
    assert page.items[0].like_count == 128


def test_comment_fetch_is_deduplicated_and_persists_limited_sample(
    client,
    app,
    auth_headers,
    workspace,
):
    inspiration_id = _seed_inspiration(app, workspace)
    headers = _headers(auth_headers, workspace)
    first = client.post(
        f"/api/v1/inspirations/{inspiration_id}/fetch-comments",
        headers=headers,
        json={"max_pages": 1},
    )
    second = client.post(
        f"/api/v1/inspirations/{inspiration_id}/fetch-comments",
        headers=headers,
        json={"max_pages": 3},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]

    requests = []

    def provider_handler(request):
        requests.append(request)
        return httpx.Response(200, json=_fixture())

    async def run_job():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(provider_handler),
        ) as http_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="test",
                client=http_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id="comment-worker",
                )

    assert asyncio.run(run_job()) is True
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/get_note_comments")
    assert requests[0].url.params["note_id"] == "comment-note"

    response = client.get(
        f"/api/v1/inspirations/{inspiration_id}/comments",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["external_comment_id"] == "comment-fixture-001"
    with app.state.database.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CommentSample)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderFetch)) == 1
        job = db.get(SyncJob, UUID(first.json()["data"]["job_id"]))
        assert job.status == "succeeded"
        assert job.result["comments_created"] == 1
