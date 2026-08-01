import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Asset, SyncJob, VideoRun
from app.jobs.errors import JobExecutionError
from app.modules.video_production.executor import (
    ensure_job_directory,
    resume_codex_composition,
    run_codex_composition,
    run_hyperframes_checks,
)
from app.providers.tts.base import TTSProvider, TTSProviderError


class VideoProductionHandler:
    def __init__(self, db: Session, *, settings: Settings, tts_provider: TTSProvider) -> None:
        self.db = db
        self.settings = settings
        self.tts_provider = tts_provider

    async def handle(self, job: SyncJob) -> dict:
        try:
            run_id = uuid.UUID(str(job.payload["video_run_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise JobExecutionError(
                code="JOB_PAYLOAD_INVALID",
                message="Video job is missing a valid video_run_id.",
                retryable=False,
            ) from exc
        run = self.db.scalar(
            select(VideoRun).where(VideoRun.id == run_id, VideoRun.workspace_id == job.workspace_id)
        )
        if run is None:
            raise JobExecutionError(
                code="NOT_FOUND", message="Video run no longer exists.", retryable=False
            )
        work_dir = ensure_job_directory(self.settings, str(run.id))
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.error_code = None
        run.error_message = None
        self.db.commit()
        try:
            self._write_request(run, work_dir)
            output = await self.tts_provider.synthesize(
                text=run.request_payload["script"], voice_id=run.voice_id
            )
            narration = work_dir / f"narration.{output.extension}"
            narration.write_bytes(output.audio)
            captions = self._captions(
                run.request_payload["script"], output.estimated_duration_seconds
            )
            (work_dir / "captions.json").write_text(
                json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            codex_execution = await run_codex_composition(self.settings, work_dir=work_dir)
            diagnostics = await self._check_with_repairs(
                work_dir=work_dir, thread_id=codex_execution.thread_id
            )
            asset = self._register_asset(run, work_dir / "final.mp4")
        except TTSProviderError as exc:
            self._fail(run, exc.code, exc.message)
            raise JobExecutionError(
                code=exc.code, message=exc.message, retryable=exc.retryable
            ) from exc
        except JobExecutionError as exc:
            self._fail(run, exc.code, exc.message)
            raise
        except OSError as exc:
            self._fail(run, "VIDEO_WORKDIR_IO", "Video work files could not be written.")
            raise JobExecutionError(
                code="VIDEO_WORKDIR_IO",
                message="Video work files could not be written.",
                retryable=True,
            ) from exc
        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.result = {
            "asset_id": str(asset.id),
            "artifact": "final.mp4",
            "artifact_path": str(
                (work_dir / "final.mp4").relative_to(Path(self.settings.video_runs_dir).resolve())
            ),
            "duration_seconds": output.estimated_duration_seconds,
            "diagnostics": {name: info["returncode"] for name, info in diagnostics.items()},
        }
        self.db.commit()
        return {"video_run_id": str(run.id), "asset_id": str(asset.id), "artifact": "final.mp4"}

    def _write_request(self, run: VideoRun, work_dir: Path) -> None:
        payload = {
            "id": str(run.id),
            "script": run.request_payload["script"],
            "instruction": run.request_payload.get("instruction"),
            "format": run.render_spec,
            "tts": {"provider": run.tts_provider, "voice_id": run.voice_id},
            "inputs": {"narration": "narration.*", "captions": "captions.json"},
            "output": "final.mp4",
        }
        (work_dir / "request.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _captions(text: str, duration_seconds: float) -> list[dict[str, object]]:
        chunks = [chunk.strip() for chunk in text.replace("\n", " ").split("。") if chunk.strip()]
        if not chunks:
            chunks = [text.strip()]
        total = sum(max(1, len(chunk)) for chunk in chunks)
        cursor = 0.0
        captions: list[dict[str, object]] = []
        for index, chunk in enumerate(chunks):
            segment = duration_seconds * max(1, len(chunk)) / total
            end = duration_seconds if index == len(chunks) - 1 else round(cursor + segment, 3)
            captions.append({"start": round(cursor, 3), "end": end, "text": chunk})
            cursor = end
        return captions

    def _register_asset(self, run: VideoRun, final_path: Path) -> Asset:
        checksum = hashlib.sha256(final_path.read_bytes()).hexdigest()
        asset = Asset(
            workspace_id=run.workspace_id,
            content_project_id=run.content_project_id,
            asset_type="video",
            storage_key=f"local-video-runs/{run.id}/final.mp4",
            mime_type="video/mp4",
            size_bytes=final_path.stat().st_size,
            checksum=checksum,
            source_type="generated",
            rights_note="Generated locally by the HyperFrames video worker.",
            created_by=run.created_by,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    async def _check_with_repairs(self, *, work_dir: Path, thread_id: str | None) -> dict:
        for repair_round in range(3):
            try:
                return await run_hyperframes_checks(self.settings, work_dir=work_dir)
            except JobExecutionError as exc:
                if exc.code != "HYPERFRAMES_CHECK_FAILED" or repair_round == 2:
                    raise
                repaired = await resume_codex_composition(
                    self.settings,
                    work_dir=work_dir,
                    thread_id=thread_id,
                    repair_round=repair_round + 1,
                )
                thread_id = repaired.thread_id
        raise AssertionError("unreachable")

    def _fail(self, run: VideoRun, code: str, message: str) -> None:
        run.status = "failed"
        run.error_code = code
        run.error_message = message
        run.finished_at = datetime.now(timezone.utc)
        self.db.commit()
