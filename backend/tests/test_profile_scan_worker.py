import asyncio
import json
import uuid
from pathlib import Path

import httpx
from sqlalchemy import func, select

from app.db.models import (
    ContentMetricSnapshot,
    ContentScore,
    ExternalContent,
    ProviderFetch,
    ProviderUsageDaily,
    SyncJob,
)
from app.jobs.worker import process_one
from app.providers.social.tikhub.client import TikHubHttpClient

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _workspace_headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_profile_scan_persists_evidence_content_metrics_and_usage(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _workspace_headers(auth_headers, workspace)
    profile = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": "profile-fixture-001",
            "profile_url": "https://www.xiaohongshu.com/user/profile/profile-fixture-001",
            "display_name": "Pending",
        },
    ).json()["data"]
    job_id = client.post(
        f"/api/v1/tracked-profiles/{profile['id']}/sync",
        headers=headers,
    ).json()["data"]["job_id"]

    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/get_user_info"):
            return httpx.Response(
                200,
                json=_fixture("xhs_profile_representative.json"),
            )
        if request.url.params.get("cursor"):
            payload = _fixture("xhs_profile_notes_representative.json")
            payload["data"]["data"]["notes"] = []
            return httpx.Response(200, json=payload)
        return httpx.Response(
            200,
            json=_fixture("xhs_profile_notes_representative.json"),
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
                    worker_id="test-worker",
                )

    assert asyncio.run(run_worker_once()) is True

    with app.state.database.session_factory() as db:
        job = db.get(SyncJob, uuid.UUID(job_id))
        assert job.status == "succeeded"
        assert job.result["contents_created"] == 1
        assert db.scalar(select(func.count()).select_from(ProviderFetch)) == 3
        assert db.scalar(select(func.count()).select_from(ExternalContent)) == 1
        assert db.scalar(select(func.count()).select_from(ContentMetricSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(ContentScore)) == 1
        request_count = db.scalar(select(func.sum(ProviderUsageDaily.request_count)))
        estimated_cost = db.scalar(select(func.sum(ProviderUsageDaily.estimated_cost_usd)))
        assert request_count == 3
        assert str(estimated_cost) == "0.003000"

    contents = client.get(
        f"/api/v1/tracked-profiles/{profile['id']}/contents",
        headers=headers,
    )
    assert contents.status_code == 200
    assert contents.json()["data"][0]["external_id"] == "note-fixture-001"

    metrics = client.get(
        f"/api/v1/tracked-profiles/{profile['id']}/metrics",
        headers=headers,
    )
    assert metrics.status_code == 200
    assert metrics.json()["data"][0]["followers"] == 12000

    sync_runs = client.get(
        f"/api/v1/tracked-profiles/{profile['id']}/sync-runs",
        headers=headers,
    )
    assert sync_runs.status_code == 200
    assert sync_runs.json()["data"][0]["id"] == job_id
    assert sync_runs.json()["data"][0]["status"] == "succeeded"
    operational_metrics = client.get("/metrics")
    assert (
        'social_ops_process_heartbeat_age_seconds{instance_id="test-worker",service="worker"}'
        in operational_metrics.text
    )
    assert requests.count("/api/v1/xiaohongshu/app_v2/get_user_posted_notes") == 2
