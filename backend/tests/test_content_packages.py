import asyncio
import json
import uuid

import httpx
from sqlalchemy import select

from app.db.models import ContentPackage, GenerationRun
from app.jobs.worker import process_one
from app.modules.content_packages.schemas import CONTENT_PACKAGE_MIN_MAX_TOKENS
from app.modules.prompts.registry import CONTENT_PACKAGE_PROMPT_REVISION
from app.providers.ai.factory import generation_provider_for_run
from app.providers.ai.generation import FixtureContentGenerationProvider
from app.providers.ai.openai_compatible import OpenAICompatibleProvider
from app.providers.social.tikhub.client import TikHubHttpClient


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _channel_and_project(client, headers):
    channel = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "Package channel",
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
    script = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
        json={
            "project_version": project["version"],
            "body": "高峰最怕漏单。检查清单三步：下单前复述、出餐后核对、交接前确认。",
            "structured_body": {
                "hook": "高峰最怕漏单。",
                "main_points": ["下单前复述", "出餐后核对", "交接前确认"],
                "call_to_action": "今晚高峰前打印这张清单。",
                "spoken_length_chars": 44,
            },
            "change_note": "Manual fixture script",
        },
    )
    assert script.status_code == 201
    refreshed = client.get(
        f"/api/v1/content-projects/{project['id']}",
        headers=headers,
    )
    assert refreshed.status_code == 200
    return channel, refreshed.json()["data"], script.json()["data"]


def _run_package_worker(app):
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
                    worker_id=f"package-worker-{uuid.uuid4()}",
                    generation_provider=FixtureContentGenerationProvider(),
                    settings=app.state.settings,
                )

    return asyncio.run(run())


def test_content_package_generation_persists_and_reads(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    _, project, script = _channel_and_project(client, headers)

    requested = client.post(
        f"/api/v1/content-projects/{project['id']}/content-packages",
        headers=headers,
        json={
            "project_version": project["version"],
            "script_version_id": script["id"],
            "target_platform": "xiaohongshu",
        },
    )
    assert requested.status_code == 202
    generation = requested.json()["data"]["generation"]
    assert generation["status"] == "queued"
    assert generation["generation_type"] == "content_package"
    assert generation["prompt_version"].endswith(f":{CONTENT_PACKAGE_PROMPT_REVISION}")

    assert _run_package_worker(app) is True

    with app.state.database.session_factory() as db:
        package = db.scalar(select(ContentPackage))
        assert package is not None
        assert package.status == "draft"
        assert package.version == 1
        assert package.target_platform == "xiaohongshu"
        assert package.package["scenes"][0]["id"] == "scene_01"
        assert package.package["narration"]["full_text"] == script["body"]
        assert f"script:{script['id']}" in package.evidence_refs
        package_id = package.id
        run = db.get(GenerationRun, uuid.UUID(generation["id"]))
        assert run.status == "succeeded"
        assert run.result["created_resource_id"] == str(package_id)

    read = client.get(f"/api/v1/content-packages/{package_id}", headers=headers)
    assert read.status_code == 200
    data = read.json()["data"]
    assert data["status"] == "draft"
    assert data["package"]["target_platform"] == "xiaohongshu"
    assert data["package"]["title_candidates"][0]["text"]
    assert len(data["package"]["scenes"]) >= 1


def test_content_package_edit_bumps_version_and_freezes(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    _, project, script = _channel_and_project(client, headers)
    requested = client.post(
        f"/api/v1/content-projects/{project['id']}/content-packages",
        headers=headers,
        json={
            "project_version": project["version"],
            "script_version_id": script["id"],
            "target_platform": "douyin",
        },
    )
    assert requested.status_code == 202
    assert _run_package_worker(app) is True

    with app.state.database.session_factory() as db:
        package_id = db.scalar(select(ContentPackage.id))

    edited = client.patch(
        f"/api/v1/content-packages/{package_id}",
        headers=headers,
        json={
            "hashtags": ["#餐厅管理", "#高峰不慌"],
            "publish_caption": "人工改过的发布文案。",
        },
    )
    assert edited.status_code == 200
    edited_data = edited.json()["data"]
    assert edited_data["version"] == 2
    assert edited_data["status"] == "draft"
    assert edited_data["package"]["hashtags"] == ["#餐厅管理", "#高峰不慌"]
    assert edited_data["package"]["scenes"][0]["id"] == "scene_01"

    frozen = client.post(
        f"/api/v1/content-packages/{edited_data['id']}/freeze",
        headers=headers,
    )
    assert frozen.status_code == 200
    assert frozen.json()["data"]["status"] == "frozen"

    with app.state.database.session_factory() as db:
        rows = db.scalars(
            select(ContentPackage).where(
                ContentPackage.content_project_id == uuid.UUID(project["id"])
            )
        ).all()
        assert {row.version for row in rows} == {1, 2}
        assert {row.status for row in rows} == {"draft", "frozen"}


def test_content_package_edit_rejects_invalid_merge(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    _, project, script = _channel_and_project(client, headers)
    requested = client.post(
        f"/api/v1/content-projects/{project['id']}/content-packages",
        headers=headers,
        json={
            "project_version": project["version"],
            "script_version_id": script["id"],
            "target_platform": "xiaohongshu",
        },
    )
    assert requested.status_code == 202
    assert _run_package_worker(app) is True
    with app.state.database.session_factory() as db:
        package_id = db.scalar(select(ContentPackage.id))

    invalid = client.patch(
        f"/api/v1/content-packages/{package_id}",
        headers=headers,
        json={"scenes": []},
    )
    assert invalid.status_code == 422


def test_list_content_packages_filters_by_platform(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    _, project, script = _channel_and_project(client, headers)
    for platform in ("douyin", "xiaohongshu"):
        requested = client.post(
            f"/api/v1/content-projects/{project['id']}/content-packages",
            headers=headers,
            json={
                "project_version": project["version"],
                "script_version_id": script["id"],
                "target_platform": platform,
            },
        )
        assert requested.status_code == 202
        assert _run_package_worker(app) is True

    listed = client.get(
        f"/api/v1/content-projects/{project['id']}/content-packages",
        headers=headers,
    )
    assert listed.status_code == 200
    assert {item["target_platform"] for item in listed.json()["data"]} == {
        "douyin",
        "xiaohongshu",
    }
    filtered = client.get(
        f"/api/v1/content-projects/{project['id']}/content-packages",
        params={"target_platform": "douyin"},
        headers=headers,
    )
    assert [item["target_platform"] for item in filtered.json()["data"]] == ["douyin"]


def test_content_package_runs_get_larger_max_tokens_floor(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.ai_provider = "fixture"
    app.state.settings.ai_model = "fixture-generation"
    headers = _headers(auth_headers, workspace)
    connection = client.post(
        "/api/v1/ai/connections",
        headers=headers,
        json={
            "name": "DeepSeek Package",
            "provider": "deepseek",
            "api_key": "sk-package-1234",
            "model": "deepseek-v4-flash",
            "use_for": ["generation"],
            "max_tokens": 2000,
        },
    )
    assert connection.status_code == 201
    connection_id = connection.json()["data"]["id"]
    _, project, script = _channel_and_project(client, headers)

    with app.state.database.session_factory() as db:
        package_run = GenerationRun(
            workspace_id=uuid.UUID(workspace["id"]),
            content_project_id=uuid.UUID(project["id"]),
            ai_connection_id=uuid.UUID(connection_id),
            generation_type="content_package",
            model_provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version="l1-v1:package-v1",
            input_hash="max-tokens-test",
            input_payload={
                "project_id": str(project["id"]),
                "project_version": project["version"],
                "script": {
                    "id": str(script["id"]),
                    "version_no": script["version_no"],
                    "body": script["body"],
                },
                "target_platform": "xiaohongshu",
                "requested_by": str(uuid.uuid4()),
            },
            evidence_refs=[f"project:{project['id']}", f"script:{script['id']}"],
        )
        db.add(package_run)
        db.flush()
        provider = generation_provider_for_run(
            db,
            run=package_run,
            settings=app.state.settings,
        )
        assert provider.provider.max_tokens == CONTENT_PACKAGE_MIN_MAX_TOKENS
        assert provider.provider.disable_thinking is True

        script_run = GenerationRun(
            workspace_id=uuid.UUID(workspace["id"]),
            content_project_id=uuid.UUID(project["id"]),
            ai_connection_id=uuid.UUID(connection_id),
            generation_type="script_draft",
            model_provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version="l1-v1:script-v3",
            input_hash="max-tokens-script-test",
            input_payload={"requested_by": str(uuid.uuid4())},
            evidence_refs=[f"project:{project['id']}"],
        )
        db.add(script_run)
        db.flush()
        script_provider = generation_provider_for_run(
            db,
            run=script_run,
            settings=app.state.settings,
        )
        assert script_provider.provider.max_tokens == 2000
        assert script_provider.provider.disable_thinking is False


def test_deepseek_content_package_sends_thinking_disabled():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"ok": True})},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            },
        )

    run = GenerationRun(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        content_project_id=uuid.uuid4(),
        generation_type="content_package",
        model_provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="l1-v1:package-v1",
        input_hash="thinking-test",
        input_payload={"target_platform": "xiaohongshu"},
        evidence_refs=["project:1"],
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.deepseek.com",
        api_key="secret-token",
        model="deepseek-v4-flash",
        timeout_seconds=30,
        json_mode=True,
        temperature=0.2,
        max_tokens=16000,
        disable_thinking=True,
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(provider.generate(run=run))
    assert seen["body"]["thinking"] == {"type": "disabled"}
