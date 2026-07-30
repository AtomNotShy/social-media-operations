import asyncio
import uuid

import httpx
from sqlalchemy import select

from app.db.models import ExternalContent
from app.jobs.worker import process_one
from app.providers.social.tikhub.client import TikHubHttpClient


def test_source_404_removes_media_but_preserves_historical_record(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = {**auth_headers, "X-Workspace-Id": workspace["id"]}
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=uuid.UUID(workspace["id"]),
            platform="bilibili",
            external_id="BV1xx411c7mD",
            canonical_url="https://www.bilibili.com/video/BV1xx411c7mD",
            content_type="video",
            title="Historical title",
            body_text="Historical analysis input",
            author_snapshot={"display_name": "Public author"},
            media_manifest=[
                {
                    "type": "video",
                    "url": "https://media.example.invalid/deleted-video.mp4",
                }
            ],
            detail_status="detail",
        )
        db.add(content)
        db.commit()

    imported = client.post(
        "/api/v1/inspirations/import-url",
        headers=headers,
        json={
            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "hydrate": "detail",
            "analyze": False,
        },
    )
    assert imported.status_code == 202

    async def run_worker():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    404,
                    json={"code": 404, "message": "not found"},
                )
            ),
        ) as raw_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="test",
                client=raw_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id="source-deletion-worker",
                )

    assert asyncio.run(run_worker()) is True
    with app.state.database.session_factory() as db:
        content = db.scalar(
            select(ExternalContent).where(ExternalContent.external_id == "BV1xx411c7mD")
        )
        assert content.deleted_at_source is not None
        assert content.media_manifest == []
        assert content.title == "Historical title"
        assert content.body_text == "Historical analysis input"
