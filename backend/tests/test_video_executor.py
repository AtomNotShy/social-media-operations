import asyncio
import os

from app.core.config import Settings
from app.jobs.errors import JobExecutionError
from app.jobs.handlers.video_production import VideoProductionHandler
from app.modules.video_production.executor import (
    CodexExecution,
    run_codex_composition,
    safe_subprocess_env,
)


class _Process:
    returncode = 0

    async def communicate(self):
        return b'{"type":"thread.started","thread_id":"thread-1"}\n', None

    def kill(self):
        pass


def test_codex_environment_excludes_provider_and_storage_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven-secret")
    monkeypatch.setenv("TIKHUB_API_KEY", "tikhub-secret")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "storage-secret")
    monkeypatch.setenv("AI_CREDENTIALS_ENCRYPTION_KEY", "ai-secret")
    monkeypatch.setenv("CODEX_API_KEY", "codex-auth")
    environment = safe_subprocess_env(include_codex_auth=True)
    assert environment["CODEX_API_KEY"] == "codex-auth"
    for name in (
        "MINIMAX_API_KEY",
        "ELEVENLABS_API_KEY",
        "TIKHUB_API_KEY",
        "OBJECT_STORAGE_SECRET_ACCESS_KEY",
        "AI_CREDENTIALS_ENCRYPTION_KEY",
    ):
        assert name not in environment

    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return _Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    work_dir = tmp_path / "run"
    work_dir.mkdir()
    (work_dir / "request.json").write_text("{}", encoding="utf-8")
    settings = Settings(app_env="test", auth_mode="development", trusted_hosts=[])
    result = asyncio.run(run_codex_composition(settings, work_dir=work_dir))
    assert result.thread_id == "thread-1"
    assert "--skip-git-repo-check" in captured["args"]
    assert "MINIMAX_API_KEY" not in captured["env"]
    assert "ELEVENLABS_API_KEY" not in captured["env"]
    assert "TIKHUB_API_KEY" not in captured["env"]
    assert "OBJECT_STORAGE_SECRET_ACCESS_KEY" not in captured["env"]
    assert "AI_CREDENTIALS_ENCRYPTION_KEY" not in captured["env"]


def test_hyperframes_environment_does_not_include_codex_auth(monkeypatch):
    monkeypatch.setenv("CODEX_API_KEY", "codex-auth")
    assert "CODEX_API_KEY" not in safe_subprocess_env(include_codex_auth=False)
    assert "CODEX_API_KEY" not in os.environ or "CODEX_API_KEY" in safe_subprocess_env(
        include_codex_auth=True
    )


def test_failed_checks_resume_same_codex_thread_at_most_twice(tmp_path, monkeypatch):
    handler = VideoProductionHandler.__new__(VideoProductionHandler)
    handler.settings = Settings(app_env="test", auth_mode="development", trusted_hosts=[])
    checks = 0
    repairs: list[tuple[str | None, int]] = []

    async def failing_then_passing(_settings, *, work_dir):
        nonlocal checks
        checks += 1
        if checks < 3:
            raise JobExecutionError(
                code="HYPERFRAMES_CHECK_FAILED", message="bad layout", retryable=True
            )
        return {"render": {"returncode": 0}}

    async def resume(_settings, *, work_dir, thread_id, repair_round):
        repairs.append((thread_id, repair_round))
        return CodexExecution(returncode=0, log_path=work_dir / "repair.jsonl", thread_id=thread_id)

    monkeypatch.setattr(
        "app.jobs.handlers.video_production.run_hyperframes_checks", failing_then_passing
    )
    monkeypatch.setattr("app.jobs.handlers.video_production.resume_codex_composition", resume)
    result = asyncio.run(handler._check_with_repairs(work_dir=tmp_path, thread_id="thread-1"))
    assert result["render"]["returncode"] == 0
    assert repairs == [("thread-1", 1), ("thread-1", 2)]
