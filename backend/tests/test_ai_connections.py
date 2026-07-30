import asyncio
import json
import threading
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from sqlalchemy import select

from app.db.models import (
    AIConnection,
    AIModelRoute,
    AnalysisRun,
    ExternalContent,
    SyncJob,
    WorkspaceInspiration,
)
from app.jobs.worker import process_one
from app.modules.ai_connections.service import resolve_route
from app.providers.ai.base import AIProviderRequestError
from app.providers.ai.openai_compatible import OpenAICompatibleProvider
from app.providers.social.tikhub.client import TikHubHttpClient


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_owner_configures_masked_encrypted_deepseek_connection(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    response = client.post(
        "/api/v1/ai/connections",
        headers=headers,
        json={
            "name": "DeepSeek Production",
            "provider": "deepseek",
            "api_key": "sk-sensitive-1234",
            "model": "deepseek-v4-flash",
            "use_for": ["l1", "l2", "generation"],
            "input_cost_per_million_usd": "0.50",
            "output_cost_per_million_usd": "2.00",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["api_key_configured"] is True
    assert data["api_key_masked"] == "••••1234"
    assert "sk-sensitive" not in response.text

    with app.state.database.session_factory() as db:
        connection = db.get(AIConnection, uuid.UUID(data["id"]))
        assert connection.encrypted_api_key != "sk-sensitive-1234"
        assert "sk-sensitive" not in connection.encrypted_api_key
        routes = db.scalars(
            select(AIModelRoute).where(AIModelRoute.connection_id == connection.id)
        ).all()
        assert {route.task_type for route in routes} == {"l1", "l2", "generation"}
        resolved = resolve_route(
            db,
            workspace_id=uuid.UUID(workspace["id"]),
            task_type="l1",
            settings=app.state.settings,
            include_secret=True,
        )
        assert resolved.provider == "deepseek"
        assert resolved.model == "deepseek-v4-flash"
        assert resolved.api_key == "sk-sensitive-1234"

    settings = client.get("/api/v1/ai/settings", headers=headers)
    assert settings.status_code == 200
    assert settings.json()["data"]["providers"][0]["provider"] == "deepseek"
    assert len(settings.json()["data"]["routes"]) == 3
    assert "sk-sensitive" not in settings.text


def test_blank_key_preserves_and_explicit_clear_removes_secret(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    created = client.post(
        "/api/v1/ai/connections",
        headers=headers,
        json={
            "name": "OpenAI",
            "provider": "openai",
            "api_key": "sk-original-5678",
            "model": "configured-model",
            "use_for": ["l1"],
        },
    ).json()["data"]

    preserved = client.patch(
        f"/api/v1/ai/connections/{created['id']}",
        headers=headers,
        json={"api_key": "", "timeout_seconds": 90},
    )
    assert preserved.status_code == 200
    assert preserved.json()["data"]["api_key_masked"] == "••••5678"

    cleared = client.patch(
        f"/api/v1/ai/connections/{created['id']}",
        headers=headers,
        json={"clear_api_key": True},
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["api_key_configured"] is False
    with app.state.database.session_factory() as db:
        connection = db.get(AIConnection, uuid.UUID(created["id"]))
        assert connection.encrypted_api_key is None


def test_openai_compatible_provider_sends_json_mode_and_parses_l1():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Evidence-backed summary",
                                    "factors": ["Strong opening"],
                                    "confidence": 0.82,
                                    "caveats": ["No transcript"],
                                    "life": "evergreen",
                                    "life_reason": "The lesson is not event-bound.",
                                    "recommended_for_l2": True,
                                }
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            },
        )

    content = ExternalContent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        platform="xiaohongshu",
        external_id="provider-test",
        canonical_url="https://www.xiaohongshu.com/explore/provider-test",
        content_type="note",
        title="Provider test",
        body_text="Source body",
        author_snapshot={},
        media_manifest=[],
    )
    run = AnalysisRun(
        id=uuid.uuid4(),
        workspace_id=content.workspace_id,
        external_content_id=content.id,
        analysis_level="l1",
        model_provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="l1-v1",
        input_hash="provider-test",
        evidence_refs=[f"content:{content.id}"],
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.deepseek.com",
        api_key="secret-token",
        model="deepseek-v4-flash",
        timeout_seconds=30,
        json_mode=True,
        temperature=Decimal("0.2"),
        max_tokens=2000,
        input_cost_per_million_usd=Decimal("1"),
        output_cost_per_million_usd=Decimal("2"),
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        provider.analyze(run=run, content=content, transcript=None, metrics={"likes": 10})
    )

    assert seen["path"] == "/chat/completions"
    assert seen["authorization"] == "Bearer secret-token"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["model"] == "deepseek-v4-flash"
    assert result.result["recommended_for_l2"] is True
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.cost_usd == Decimal("0.002")


def test_openai_compatible_provider_maps_auth_failure_without_leaking_body():
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.test/v1",
        api_key="bad-secret",
        model="model-a",
        timeout_seconds=30,
        json_mode=True,
        temperature=Decimal("0"),
        max_tokens=512,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(401, json={"error": {"message": "echo bad-secret"}})
        ),
    )

    try:
        asyncio.run(provider.list_models())
    except AIProviderRequestError as exc:
        assert exc.code == "AI_AUTH_FAILED"
        assert exc.retryable is False
        assert "bad-secret" not in exc.message
    else:
        raise AssertionError("Expected AIProviderRequestError")


def test_configured_connection_runs_l1_end_to_end_through_worker(
    client,
    app,
    auth_headers,
    workspace,
):
    class ModelHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            assert self.path == "/v1/chat/completions"
            assert body["model"] == "local-compatible-model"
            result = {
                "summary": "End-to-end configured model result",
                "factors": ["The configured provider received source evidence."],
                "confidence": 0.9,
                "caveats": ["Local protocol smoke test."],
                "life": "evergreen",
                "life_reason": "The operational lesson is not time-bound.",
                "recommended_for_l2": False,
            }
            payload = json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": json.dumps(result)},
                        }
                    ],
                    "usage": {"prompt_tokens": 321, "completion_tokens": 123},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        headers = _headers(auth_headers, workspace)
        connection = client.post(
            "/api/v1/ai/connections",
            headers=headers,
            json={
                "name": "Local compatible",
                "provider": "openai_compatible",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "local-compatible-model",
                "use_for": ["l1"],
            },
        ).json()["data"]
        workspace_id = uuid.UUID(workspace["id"])
        with app.state.database.session_factory() as db:
            content = ExternalContent(
                workspace_id=workspace_id,
                platform="xiaohongshu",
                external_id="configured-provider-e2e",
                canonical_url="https://www.xiaohongshu.com/explore/configured-provider-e2e",
                content_type="note",
                title="Configured provider E2E",
                body_text="Evidence supplied to the configured model.",
                author_snapshot={},
                media_manifest=[],
            )
            db.add(content)
            db.flush()
            inspiration = WorkspaceInspiration(
                workspace_id=workspace_id,
                external_content_id=content.id,
                source="test",
            )
            db.add(inspiration)
            db.commit()
            inspiration_id = inspiration.id

        accepted = client.post(
            f"/api/v1/inspirations/{inspiration_id}/analyze",
            headers=headers,
            json={"level": "l1"},
        )
        assert accepted.status_code == 202
        analysis = accepted.json()["data"]["analysis"]
        assert analysis["ai_connection_id"] == connection["id"]

        async def run_worker():
            async with httpx.AsyncClient(
                base_url="https://api.example.test",
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(500, json={"unused": True})
                ),
            ) as raw_client:
                tikhub = TikHubHttpClient(
                    base_url="https://api.example.test",
                    api_key="unused",
                    client=raw_client,
                )
                with app.state.database.session_factory() as db:
                    return await process_one(
                        db,
                        client=tikhub,
                        worker_id="configured-ai-worker",
                        settings=app.state.settings,
                    )

        assert asyncio.run(run_worker()) is True
        completed = client.get(f"/api/v1/analyses/{analysis['id']}", headers=headers)
        assert completed.json()["data"]["status"] == "succeeded"
        assert completed.json()["data"]["result"]["summary"].startswith("End-to-end")
        with app.state.database.session_factory() as db:
            job = db.get(SyncJob, uuid.UUID(analysis["sync_job_id"]))
            assert job.status == "succeeded"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
