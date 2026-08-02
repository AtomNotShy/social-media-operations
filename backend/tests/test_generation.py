import asyncio
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.db.models import (
    AIAttemptLog,
    AICostLedger,
    ExternalContent,
    GenerationRun,
    ReviewInsight,
    ScriptVersion,
    SyncJob,
    WorkspaceInspiration,
)
from app.jobs.worker import process_one
from app.modules.prompts.registry import SCRIPT_GENERATION_PROMPT_REVISION
from app.providers.ai.generation import FixtureContentGenerationProvider
from app.providers.social.tikhub.client import TikHubHttpClient


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _channel_and_project(client, headers):
    channel = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "Generation channel",
            "positioning": "Restaurant operations education",
            "tone_rules": ["direct", "evidence-led"],
        },
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "title": "Reduce missed orders",
        },
    ).json()["data"]
    return channel, project


def _run_generation_worker(app):
    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(lambda _: httpx.Response(500, json={"unexpected": True})),
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
                    worker_id=f"generation-worker-{uuid.uuid4()}",
                    generation_provider=FixtureContentGenerationProvider(),
                    settings=app.state.settings,
                )

    return asyncio.run(run())


def test_script_generation_is_audited_budgeted_and_append_only(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    _, project = _channel_and_project(client, headers)

    requested = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts/generate",
        headers=headers,
        json={
            "project_version": project["version"],
            "instruction": "Use a pain-led opening and cite only supplied context.",
        },
    )
    assert requested.status_code == 202
    generation = requested.json()["data"]["generation"]
    assert generation["status"] == "queued"
    assert generation["prompt_version"].endswith(f":{SCRIPT_GENERATION_PROMPT_REVISION}")

    assert _run_generation_worker(app) is True

    completed = client.get(
        f"/api/v1/generation-runs/{generation['id']}",
        headers=headers,
    )
    assert completed.status_code == 200
    completed_data = completed.json()["data"]
    assert completed_data["status"] == "succeeded"
    assert completed_data["result"]["created_resource_id"]
    assert f"project:{project['id']}" in completed_data["evidence_refs"]

    scripts = client.get(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
    ).json()["data"]
    assert len(scripts) == 1
    assert scripts[0]["generation_run_id"] == generation["id"]
    assert scripts[0]["version_no"] == 1

    with app.state.database.session_factory() as db:
        run = db.get(GenerationRun, uuid.UUID(generation["id"]))
        ledger = db.scalar(select(AICostLedger).where(AICostLedger.sync_job_id == run.sync_job_id))
        job = db.get(SyncJob, run.sync_job_id)
        attempt = db.scalar(
            select(AIAttemptLog).where(
                AIAttemptLog.sync_job_id == run.sync_job_id,
                AIAttemptLog.attempt_no == job.attempt,
            )
        )
        assert ledger.status == "settled"
        assert ledger.resource_type == "generation"
        assert attempt is not None
        assert attempt.status == "succeeded"
        assert attempt.model == "fixture-generation"
        assert attempt.cost_usd == 0
        assert db.scalar(select(ScriptVersion).where(ScriptVersion.generation_run_id == run.id))


def test_script_generation_resolves_topic_source_materials(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    channel = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "Source channel",
            "positioning": "Oral English learning",
        },
    ).json()["data"]
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=uuid.UUID(workspace["id"]),
            platform="x",
            external_id="source-oral-english",
            canonical_url="https://x.com/source/status/1",
            content_type="article",
            title="每天练口语的原文",
            body_text="原文正文：外教课一年两万，GPT Live 当陪练，Obsidian 记复盘。",
            author_snapshot={"handle": "source", "display_name": "Source"},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        inspiration = WorkspaceInspiration(
            workspace_id=uuid.UUID(workspace["id"]),
            external_content_id=content.id,
            source="manual_url",
        )
        db.add(inspiration)
        db.commit()
        inspiration_id = str(inspiration.id)
        content_id = str(content.id)

    topic = client.post(
        f"/api/v1/topics/from-inspiration/{inspiration_id}",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "title": "每天练口语，却总觉得没进步？",
            "angle": "用 GPT Live + Obsidian 把每次开口变成可追踪的成长记录",
            "hook": "谁还不知道GPT可以这么用",
        },
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "topic_id": topic["id"],
            "title": topic["title"],
        },
    ).json()["data"]

    requested = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts/generate",
        headers=headers,
        json={"project_version": project["version"]},
    )
    assert requested.status_code == 202
    generation = requested.json()["data"]["generation"]

    with app.state.database.session_factory() as db:
        run = db.get(GenerationRun, uuid.UUID(generation["id"]))
        materials = run.input_payload["source_materials"]
        assert [unit["ref"] for unit in materials] == [f"content:{content_id}"]
        assert (
            materials[0]["body"]
            == "原文正文：外教课一年两万，GPT Live 当陪练，Obsidian 记复盘。"
        )
        assert materials[0]["title"] == "每天练口语的原文"
        assert f"content:{content_id}" in run.evidence_refs
        assert run.input_payload["topic"]["evidence_refs"] == [
            f"inspiration:{inspiration_id}",
            f"content:{content_id}",
        ]

    assert _run_generation_worker(app) is True
    completed = client.get(
        f"/api/v1/generation-runs/{generation['id']}",
        headers=headers,
    ).json()["data"]
    assert completed["status"] == "succeeded"
    assert f"content:{content_id}" in completed["evidence_refs"]


def test_script_generation_rejects_unresolvable_topic_evidence(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    channel = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "Dangling channel",
        },
    ).json()["data"]
    missing_content_id = uuid.uuid4()
    topic = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "title": "悬空证据选题",
            "evidence_refs": [f"content:{missing_content_id}"],
        },
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "topic_id": topic["id"],
            "title": topic["title"],
        },
    ).json()["data"]

    response = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts/generate",
        headers=headers,
        json={"project_version": project["version"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EVIDENCE_UNAVAILABLE"
    with app.state.database.session_factory() as db:
            assert (
                db.scalar(
                    select(GenerationRun).where(
                        GenerationRun.content_project_id == uuid.UUID(project["id"])
                    )
                )
                is None
            )


def test_generation_emergency_stop_rejects_before_job_creation(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    _, project = _channel_and_project(client, headers)
    assert (
        client.post(
            f"/api/v1/workspaces/{workspace['id']}/external-calls/pause",
            headers=auth_headers,
            json={"reason": "Cost incident"},
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts/generate",
        headers=headers,
        json={"project_version": project["version"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EXTERNAL_CALLS_PAUSED"
    with app.state.database.session_factory() as db:
        assert db.scalar(select(SyncJob).where(SyncJob.job_type == "CONTENT_GENERATION")) is None
        assert db.scalar(select(GenerationRun)) is None
        assert db.scalar(select(AICostLedger)) is None


def test_review_generation_creates_evidence_backed_review(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    channel, project = _channel_and_project(client, headers)
    script = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
        json={"project_version": 1, "body": "Manual approved script."},
    ).json()["data"]
    producing = client.post(
        f"/api/v1/content-projects/{project['id']}/transition",
        headers=headers,
        json={"from": "scripting", "to": "producing", "version": 2},
    ).json()["data"]
    reviewed = client.post(
        f"/api/v1/content-projects/{project['id']}/transition",
        headers=headers,
        json={"from": "producing", "to": "review", "version": producing["version"]},
    ).json()["data"]
    plan = client.post(
        "/api/v1/publish-plans",
        headers=headers,
        json={
            "content_project_id": project["id"],
            "owned_channel_id": channel["id"],
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "publish_payload": {"title": "Published fixture"},
        },
    ).json()["data"]
    approved = client.post(
        f"/api/v1/publish-plans/{plan['id']}/approve",
        headers=headers,
    ).json()["data"]
    package = client.post(
        f"/api/v1/publish-plans/{plan['id']}/publish",
        headers=headers,
    ).json()["data"]
    record = client.post(
        f"/api/v1/publish-plans/{plan['id']}/mark-published",
        headers=headers,
        json={
            "version": package["plan_version"],
            "published_url": "https://www.xiaohongshu.com/explore/generated-review",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "matched_publish_package": True,
        },
    ).json()["data"]
    assert script["version_no"] == 1
    assert reviewed["status"] == "review"
    assert approved["status"] == "approved"

    requested = client.post(
        f"/api/v1/publish-records/{record['id']}/reviews/generate",
        headers=headers,
        json={
            "review_window": "24h",
            "metrics": {"views": 2000, "likes": 100, "qualified_leads": 4},
            "primary_metric": "qualified_leads",
        },
    )
    assert requested.status_code == 202
    generation_id = requested.json()["data"]["generation"]["id"]
    assert _run_generation_worker(app) is True

    with app.state.database.session_factory() as db:
        run = db.get(GenerationRun, uuid.UUID(generation_id))
        job = db.get(SyncJob, run.sync_job_id)
        assert run.input_payload["script"]["body"] == "Manual approved script."
        assert run.input_payload["script"]["version_no"] == 1
        assert run.input_payload["publish_payload"]["title"] == "Published fixture"
        assert f"script:{script['id']}" in run.evidence_refs
        review = db.scalar(
            select(ReviewInsight).where(ReviewInsight.publish_record_id == uuid.UUID(record["id"]))
        )
        assert run.status == "succeeded"
        assert job.status == "succeeded"
        assert review.metrics["qualified_leads"] == 4
        assert review.next_actions
        assert run.result["created_resource_id"] == str(review.id)
