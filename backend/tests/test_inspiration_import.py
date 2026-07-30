import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import func, select

from app.db.models import (
    AnalysisRun,
    ContentScore,
    ExternalContent,
    ProviderFetch,
    SyncJob,
    WorkspaceInspiration,
)
from app.jobs.worker import process_one
from app.providers.social.tikhub.client import TikHubHttpClient

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _workspace_headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_duplicate_url_import_reuses_active_job_then_fresh_content(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    url = "https://www.xiaohongshu.com/explore/note-detail-fixture-001?source=web"

    first = client.post(
        "/api/v1/inspirations/import-url",
        headers=headers,
        json={"url": url, "hydrate": "detail", "analyze": False},
    )
    second = client.post(
        "/api/v1/inspirations/import-url",
        headers=headers,
        json={"url": url, "hydrate": "detail", "analyze": False},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]

    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(
            200,
            json=_fixture("xhs_content_detail_representative.json"),
        )

    async def run_worker_once():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="secret-test-token",
                client=raw_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id="test-import-worker",
                )

    assert asyncio.run(run_worker_once()) is True

    third = client.post(
        "/api/v1/inspirations/import-url",
        headers=headers,
        json={"url": url, "hydrate": "detail", "analyze": False},
    )

    assert third.status_code == 200
    assert third.json()["data"]["existing"] is True
    assert third.json()["data"]["job_id"] is None
    assert requests == ["/api/v1/xiaohongshu/app_v2/get_image_note_detail"]

    inspirations = client.get("/api/v1/inspirations", headers=headers)
    assert inspirations.status_code == 200
    assert inspirations.json()["data"][0]["content"]["detail_status"] == "detail"

    with app.state.database.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(SyncJob)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderFetch)) == 1
        assert db.scalar(select(func.count()).select_from(ExternalContent)) == 1
        assert db.scalar(select(func.count()).select_from(WorkspaceInspiration)) == 1
        assert db.scalar(select(func.count()).select_from(ContentScore)) == 1
        job = db.scalar(select(SyncJob))
        assert job.result["score_grade"] == "insufficient"

    refresh = client.post(
        f"/api/v1/inspirations/{third.json()['data']['inspiration_id']}/refresh-metrics",
        headers=headers,
    )
    hydrate = client.post(
        f"/api/v1/inspirations/{third.json()['data']['inspiration_id']}/hydrate-detail",
        headers=headers,
    )
    assert refresh.status_code == 202
    assert hydrate.status_code == 202
    assert refresh.json()["data"]["job_id"] == hydrate.json()["data"]["job_id"]


def test_explicit_analysis_request_queues_l1_only_when_configured(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-l1"
    headers = _workspace_headers(auth_headers, workspace)
    response = client.post(
        "/api/v1/inspirations/import-url",
        headers=headers,
        json={
            "url": "https://www.xiaohongshu.com/explore/analysis-detail-fixture",
            "hydrate": "detail",
            "analyze": True,
        },
    )
    assert response.status_code == 202

    def handler(_: httpx.Request) -> httpx.Response:
        payload = _fixture("xhs_content_detail_representative.json")
        payload["data"]["data"]["note_id"] = "analysis-detail-fixture"
        return httpx.Response(200, json=payload)

    async def run_detail():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
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
                    worker_id="analysis-detail-worker",
                    settings=app.state.settings,
                )

    assert asyncio.run(run_detail()) is True
    with app.state.database.session_factory() as db:
        jobs = db.scalars(select(SyncJob).order_by(SyncJob.created_at)).all()
        assert [job.job_type for job in jobs] == [
            "CONTENT_DETAIL_FETCH",
            "AI_ANALYSIS",
        ]
        assert jobs[0].result["analysis_status"] == "queued"
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 1
