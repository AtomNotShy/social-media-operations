import asyncio
import base64
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base, VideoRun
from app.jobs.video_worker import process_one
from app.main import create_app
from app.modules.video_production.executor import CodexExecution, ensure_job_directory


def _settings(video_dir: Path) -> Settings:
    return Settings(
        app_env="test",
        auth_mode="development",
        database_url="sqlite:///:memory:",
        trusted_hosts=[],
        video_tts_provider="fixture",
        video_runs_dir=str(video_dir),
        ai_credentials_encryption_key=base64.urlsafe_b64encode(b"test-key" * 4).decode(),
    )


def _project(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    workspace = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Video", "timezone": "UTC"}
    ).json()["data"]
    workspace_headers = {**headers, "X-Workspace-Id": workspace["id"]}
    channel = client.post(
        "/api/v1/owned-channels",
        headers=workspace_headers,
        json={"platform": "xiaohongshu", "display_name": "Video channel"},
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=workspace_headers,
        json={"owned_channel_id": channel["id"], "title": "Video project"},
    ).json()["data"]
    script = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=workspace_headers,
        json={"project_version": project["version"], "body": "第一句。第二句。"},
    ).json()["data"]
    return workspace_headers["X-Workspace-Id"], script["id"]


def test_video_request_deduplicates_and_worker_registers_local_artifact(tmp_path, monkeypatch):
    settings = _settings(tmp_path / "video-runs")
    application = create_app(settings)
    Base.metadata.create_all(application.state.database.engine)
    headers = {"Authorization": "Bearer dev:video-owner"}

    async def fake_codex(_settings, *, work_dir):
        (work_dir / "DESIGN.md").write_text("# Design", encoding="utf-8")
        (work_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        return CodexExecution(returncode=0, log_path=work_dir / "codex.jsonl", thread_id="test")

    async def fake_checks(_settings, *, work_dir):
        (work_dir / "final.mp4").write_bytes(b"fake-mp4")
        return {step: {"returncode": 0} for step in ("lint", "validate", "inspect", "render")}

    monkeypatch.setattr("app.jobs.handlers.video_production.run_codex_composition", fake_codex)
    monkeypatch.setattr("app.jobs.handlers.video_production.run_hyperframes_checks", fake_checks)

    with TestClient(application) as client:
        workspace_id, script_id = _project(client, headers)
        project_id = client.get(
            "/api/v1/content-projects", headers={**headers, "X-Workspace-Id": workspace_id}
        ).json()["data"][0]["id"]
        body = {"script_version_id": script_id, "render_spec": {"style": "dark-tech"}}
        first = client.post(
            f"/api/v1/content-projects/{project_id}/videos",
            headers={**headers, "X-Workspace-Id": workspace_id},
            json=body,
        )
        assert first.status_code == 202
        run_id = first.json()["data"]["video_run"]["id"]
        duplicate = client.post(
            f"/api/v1/content-projects/{project_id}/videos",
            headers={**headers, "X-Workspace-Id": workspace_id},
            json=body,
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["data"]["reused"] is True

        with application.state.database.session_factory() as db:
            assert asyncio.run(process_one(db, settings=settings, worker_id="test-video-worker"))
            run = db.get(VideoRun, uuid.UUID(run_id))
            assert run is not None and run.status == "succeeded"
            assert run.result and run.result["artifact"] == "final.mp4"

        response = client.get(
            f"/api/v1/content-projects/{project_id}/videos/{run_id}/artifact",
            headers={**headers, "X-Workspace-Id": workspace_id},
        )
        assert response.status_code == 200
        assert response.content == b"fake-mp4"


def test_work_directory_is_scoped_to_video_runs_root(tmp_path):
    settings = _settings(tmp_path / "video-runs")
    directory = ensure_job_directory(settings, "valid-run")
    assert directory.parent == (tmp_path / "video-runs").resolve()
    try:
        ensure_job_directory(settings, "../outside")
    except Exception as exc:
        assert getattr(exc, "code", None) == "VIDEO_WORKDIR_INVALID"
    else:
        raise AssertionError("A traversal run id must be rejected")


def test_elevenlabs_voice_uses_config_default_or_rejects_missing_value(tmp_path):
    headers = {"Authorization": "Bearer dev:eleven-owner"}
    configured = Settings(
        app_env="test",
        auth_mode="development",
        database_url="sqlite:///:memory:",
        trusted_hosts=[],
        video_tts_provider="elevenlabs",
        elevenlabs_api_key="test-key",
        elevenlabs_voice_id="configured-voice",
        video_runs_dir=str(tmp_path / "configured"),
    )
    application = create_app(configured)
    Base.metadata.create_all(application.state.database.engine)
    with TestClient(application) as client:
        workspace_id, script_id = _project(client, headers)
        project_id = client.get(
            "/api/v1/content-projects", headers={**headers, "X-Workspace-Id": workspace_id}
        ).json()["data"][0]["id"]
        response = client.post(
            f"/api/v1/content-projects/{project_id}/videos",
            headers={**headers, "X-Workspace-Id": workspace_id},
            json={"script_version_id": script_id},
        )
        assert response.status_code == 202
        assert response.json()["data"]["video_run"]["voice_id"] == "configured-voice"

    missing = Settings(
        app_env="test",
        auth_mode="development",
        database_url="sqlite:///:memory:",
        trusted_hosts=[],
        video_tts_provider="elevenlabs",
        elevenlabs_api_key="test-key",
        video_runs_dir=str(tmp_path / "missing"),
    )
    application = create_app(missing)
    Base.metadata.create_all(application.state.database.engine)
    with TestClient(application) as client:
        workspace_id, script_id = _project(client, headers)
        project_id = client.get(
            "/api/v1/content-projects", headers={**headers, "X-Workspace-Id": workspace_id}
        ).json()["data"][0]["id"]
        response = client.post(
            f"/api/v1/content-projects/{project_id}/videos",
            headers={**headers, "X-Workspace-Id": workspace_id},
            json={"script_version_id": script_id},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "ELEVENLABS_VOICE_NOT_CONFIGURED"
