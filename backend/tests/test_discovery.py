import asyncio
import json
from pathlib import Path

import httpx

from app.jobs.worker import process_one
from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.xiaohongshu import XiaohongshuAppV2Adapter

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture():
    return json.loads((FIXTURES / "xhs_search_representative.json").read_text(encoding="utf-8"))


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _search(client, headers):
    return client.post(
        "/api/v1/discover/search",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "query": "餐饮运营",
            "max_pages": 2,
            "hydrate_top": 0,
        },
    )


def test_representative_search_fixture_is_normalized():
    page = XiaohongshuAppV2Adapter().parse_search_results(_fixture())

    assert page.search_id == "fixture-search-id"
    assert page.search_session_id == "fixture-session-id"
    assert page.has_more is False
    assert page.items[0].external_id == "search-note-fixture-001"
    assert page.items[0].metrics.favorites == 150


def test_search_stays_separate_until_selected_import(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    estimate = client.get(
        "/api/v1/discover/search-estimate?max_pages=2",
        headers=headers,
    )
    assert estimate.status_code == 200
    assert estimate.json()["data"] == {
        "provider_calls": 2,
        "estimated_provider_cost_usd": "0.002",
    }
    first = _search(client, headers)
    second = _search(client, headers)
    assert first.status_code == 202
    assert first.json()["data"]["estimated_provider_cost_usd"] == "0.002"
    assert second.json()["data"]["job_id"] == first.json()["data"]["job_id"]
    assert second.json()["data"]["search_id"] == first.json()["data"]["search_id"]
    job_id = first.json()["data"]["job_id"]

    def provider_handler(request):
        assert request.url.path.endswith("/search_notes")
        assert request.url.params["keyword"] == "餐饮运营"
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
                    worker_id="discovery-worker",
                )

    assert asyncio.run(run_job()) is True

    inspirations_before = client.get("/api/v1/inspirations", headers=headers)
    assert inspirations_before.json()["data"] == []
    search = client.get(f"/api/v1/discover/search-jobs/{job_id}", headers=headers)
    assert search.status_code == 200
    data = search.json()["data"]
    assert data["status"] == "succeeded"
    assert data["result_count"] == 1
    assert data["results"][0]["imported_external_content_id"] is None

    imported = client.post(
        f"/api/v1/discover/search-jobs/{job_id}/import",
        headers=headers,
        json={"result_ids": [data["results"][0]["id"]], "hydrate": False},
    )
    assert imported.status_code == 200
    assert len(imported.json()["data"]["inspiration_ids"]) == 1
    assert imported.json()["data"]["hydration_job_ids"] == []
    inspirations_after = client.get("/api/v1/inspirations", headers=headers)
    assert inspirations_after.json()["data"][0]["content"]["external_id"] == (
        "search-note-fixture-001"
    )

    trending = client.get("/api/v1/discover/trending", headers=headers)
    assert trending.status_code == 200
    trend = trending.json()["data"][0]
    assert trend["external_id"] == "search-note-fixture-001"
    assert trend["source"] == "workspace_metric_snapshot"
    assert trend["evidence_snapshot_id"]
    assert trend["trend_score"] > 0


def test_trending_refresh_queues_active_profile_scans(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    profile = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": "trending-profile",
            "profile_url": "https://www.xiaohongshu.com/user/profile/trending-profile",
            "display_name": "Trending profile",
        },
    ).json()["data"]
    first = client.post("/api/v1/discover/trending/refresh", headers=headers)
    second = client.post("/api/v1/discover/trending/refresh", headers=headers)

    assert first.status_code == 202
    assert first.json()["data"]["queued_job_ids"] == second.json()["data"]["queued_job_ids"]
    sync_runs = client.get(
        f"/api/v1/tracked-profiles/{profile['id']}/sync-runs",
        headers=headers,
    )
    assert len(sync_runs.json()["data"]) == 1
