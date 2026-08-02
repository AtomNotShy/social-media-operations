import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import select

from app.db.models import SyncJob
from app.jobs.worker import process_one
from app.providers.social.tikhub.client import TikHubHttpClient

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _create_channel(client, headers, **overrides):
    payload = {
        "platform": "xiaohongshu",
        "display_name": "待验证账号",
        "handle": "@pending",
        "external_id": "profile-fixture-001",
        **overrides,
    }
    response = client.post("/api/v1/owned-channels", headers=headers, json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def test_creating_channel_without_external_id_stays_idle(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers, external_id=None)
    assert channel["sync_status"] == "idle"
    assert channel["sync_error"] is None
    assert channel["avatar_url"] is None
    assert channel["last_synced_at"] is None


def test_creating_channel_enqueues_scan_and_persists_profile(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers)
    assert channel["sync_status"] == "pending"

    with app.state.database.session_factory() as db:
        job = db.scalar(
            select(SyncJob).where(
                SyncJob.dedupe_key == f"owned-channel-scan:{channel['id']}"
            )
        )
        assert job is not None
        assert job.job_type == "OWNED_CHANNEL_SCAN"
        job_id = job.id

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/get_user_info"):
            return httpx.Response(
                200,
                json=_fixture("xhs_profile_representative.json"),
            )
        raise AssertionError(f"Unexpected request: {request.url}")

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
        job = db.get(SyncJob, job_id)
        assert job.status == "succeeded"
        updated = client.get(
            f"/api/v1/owned-channels/{channel['id']}",
            headers=headers,
        ).json()["data"]
        assert updated["sync_status"] == "synced"
        assert updated["sync_error"] is None
        assert updated["display_name"] == "JeremyLin林书豪"
        assert updated["avatar_url"] == (
            "https://sns-avatar-qc.rednotecdn.com/avatar/623d98cdbda33525f18be3a0.jpg?"
            "imageView2/2/w/540/format/webp"
        )
        assert updated["bio"] == "职业篮球运动员"
        assert updated["handle"] == "1429907658"
        assert updated["last_synced_at"] is not None


def test_manual_rescan_endpoint_queues_job(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers)
    response = client.post(
        f"/api/v1/owned-channels/{channel['id']}/scan",
        headers=headers,
    )
    assert response.status_code == 202
    assert response.json()["data"]["job_id"]

    rescan = client.post(
        f"/api/v1/owned-channels/{channel['id']}/scan",
        headers=headers,
    )
    assert rescan.status_code == 202
    assert rescan.json()["data"]["job_id"] == response.json()["data"]["job_id"]

    refreshed = client.get(
        f"/api/v1/owned-channels/{channel['id']}",
        headers=headers,
    ).json()["data"]
    assert refreshed["sync_status"] == "pending"


def test_unsupported_platform_marks_channel_error_without_retry(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers, platform="youtube")
    assert channel["sync_status"] == "pending"

    async def run_worker_once():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
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

    refreshed = client.get(
        f"/api/v1/owned-channels/{channel['id']}",
        headers=headers,
    ).json()["data"]
    assert refreshed["sync_status"] == "error"
    assert "暂不支持自动扫描" in refreshed["sync_error"]


def test_scan_without_external_id_is_rejected(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers, external_id=None)
    response = client.post(
        f"/api/v1/owned-channels/{channel['id']}/scan",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
