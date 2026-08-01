import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.jobs.errors import JobExecutionError


@dataclass(frozen=True, slots=True)
class CodexExecution:
    returncode: int
    log_path: Path
    thread_id: str | None


_SAFE_ENV_NAMES = {
    "HOME",
    "LOGNAME",
    "PATH",
    "SHELL",
    "TERM",
    "TMPDIR",
    "TMP",
    "TEMP",
    "USER",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_RUNTIME_DIR",
}


def safe_subprocess_env(*, include_codex_auth: bool) -> dict[str, str]:
    """Pass only runtime variables; never inherit app/provider secrets by default."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in _SAFE_ENV_NAMES or name.startswith("LC_")
    }
    if include_codex_auth:
        for name in ("CODEX_HOME", "CODEX_API_KEY"):
            value = os.environ.get(name)
            if value:
                environment[name] = value
    return environment


def _thread_id_from_jsonl(raw: bytes) -> str | None:
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
            return event["thread_id"]
    return None


def ensure_job_directory(settings: Settings, run_id: str) -> Path:
    root = Path(settings.video_runs_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = (root / run_id).resolve()
    if root not in directory.parents or directory == root:
        raise JobExecutionError(
            code="VIDEO_WORKDIR_INVALID",
            message="Video work directory is outside the configured video-runs root.",
            retryable=False,
        )
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory


async def run_codex_composition(settings: Settings, *, work_dir: Path) -> CodexExecution:
    request_path = work_dir / "request.json"
    if not request_path.is_file():
        raise JobExecutionError(
            code="VIDEO_REQUEST_MISSING",
            message="Video request manifest is missing.",
            retryable=False,
        )
    prompt = (
        "Read request.json in the current directory. Use the HyperFrames skill to create a "
        "single self-contained composition for this request. First create DESIGN.md with the "
        "visual identity, then create index.html and only write files inside the current "
        "directory. Use narration.* and captions.json from this directory. Do not read or write "
        "outside this directory, do not access secrets or environment files, and do not call "
        "external TTS services. The composition must follow the request dimensions and include "
        "transitions, captions, and registered GSAP timelines. Stop after authoring; the worker "
        "will run lint, validate, inspect, and render."
    )
    log_path = work_dir / "codex.jsonl"
    try:
        process = await asyncio.create_subprocess_exec(
            settings.video_codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--json",
            prompt,
            cwd=str(work_dir),
            env=safe_subprocess_env(include_codex_auth=True),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        raise JobExecutionError(
            code="CODEX_UNAVAILABLE", message="Codex executable is not available.", retryable=False
        ) from exc
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(), timeout=settings.video_codex_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise JobExecutionError(
            code="CODEX_TIMEOUT", message="Codex composition generation timed out.", retryable=True
        ) from exc
    log_path.write_bytes(stdout or b"")
    if process.returncode != 0:
        raise JobExecutionError(
            code="CODEX_COMPOSITION_FAILED",
            message="Codex could not generate the HyperFrames composition; see codex.jsonl.",
            retryable=True,
        )
    return CodexExecution(
        returncode=process.returncode,
        log_path=log_path,
        thread_id=_thread_id_from_jsonl(stdout or b""),
    )


async def resume_codex_composition(
    settings: Settings, *, work_dir: Path, thread_id: str | None, repair_round: int
) -> CodexExecution:
    if not thread_id:
        raise JobExecutionError(
            code="CODEX_THREAD_ID_MISSING",
            message="Codex did not emit a resumable thread id for the failed video check.",
            retryable=False,
        )
    prompt = (
        "Read diagnostics.json in the current directory, fix the HyperFrames composition it "
        "describes, and only write files in the current directory. Preserve request.json, "
        "narration, and captions. Do not access secrets, environment files, or external TTS "
        "services. Stop "
        "after the composition repair; the worker will rerun checks."
    )
    log_path = work_dir / f"codex-repair-{repair_round}.jsonl"
    try:
        process = await asyncio.create_subprocess_exec(
            settings.video_codex_bin,
            "exec",
            "resume",
            "--skip-git-repo-check",
            "--json",
            thread_id,
            prompt,
            cwd=str(work_dir),
            env=safe_subprocess_env(include_codex_auth=True),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        raise JobExecutionError(
            code="CODEX_UNAVAILABLE", message="Codex executable is not available.", retryable=False
        ) from exc
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(), timeout=settings.video_codex_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise JobExecutionError(
            code="CODEX_TIMEOUT", message="Codex composition repair timed out.", retryable=True
        ) from exc
    log_path.write_bytes(stdout or b"")
    if process.returncode != 0:
        raise JobExecutionError(
            code="CODEX_REPAIR_FAILED",
            message="Codex could not repair the HyperFrames composition; see its repair log.",
            retryable=True,
        )
    return CodexExecution(
        returncode=process.returncode,
        log_path=log_path,
        thread_id=_thread_id_from_jsonl(stdout or b"") or thread_id,
    )


async def run_hyperframes_checks(settings: Settings, *, work_dir: Path) -> dict:
    commands = {
        "lint": [settings.video_hyperframes_bin, "hyperframes", "lint"],
        "validate": [settings.video_hyperframes_bin, "hyperframes", "validate"],
        "inspect": [settings.video_hyperframes_bin, "hyperframes", "inspect", "--json"],
        "render": [
            settings.video_hyperframes_bin,
            "hyperframes",
            "render",
            "--output",
            "final.mp4",
        ],
    }
    diagnostics: dict[str, dict[str, object]] = {}
    for step, command in commands.items():
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(work_dir),
                env=safe_subprocess_env(include_codex_auth=False),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await asyncio.wait_for(
                process.communicate(), timeout=settings.video_hyperframes_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise JobExecutionError(
                code="HYPERFRAMES_TIMEOUT", message=f"HyperFrames {step} timed out.", retryable=True
            ) from exc
        except OSError as exc:
            raise JobExecutionError(
                code="HYPERFRAMES_UNAVAILABLE",
                message="HyperFrames CLI is not available.",
                retryable=False,
            ) from exc
        text = (output or b"").decode("utf-8", errors="replace")
        diagnostics[step] = {"returncode": process.returncode, "output": text[-8000:]}
        if process.returncode != 0:
            (work_dir / "diagnostics.json").write_text(
                json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            raise JobExecutionError(
                code="HYPERFRAMES_CHECK_FAILED",
                message=f"HyperFrames {step} failed; see diagnostics.json.",
                retryable=step != "lint",
            )
    (work_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not (work_dir / "final.mp4").is_file():
        raise JobExecutionError(
            code="VIDEO_RENDER_MISSING",
            message="HyperFrames did not produce final.mp4.",
            retryable=True,
        )
    return diagnostics
