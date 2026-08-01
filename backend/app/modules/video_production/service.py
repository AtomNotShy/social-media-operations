import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import ScriptVersion, VideoRun
from app.jobs.service import create_job
from app.modules.video_production.schemas import VideoRunCreate
from app.modules.workflow.service import get_project


def create_video_run(
    db: Session,
    *,
    settings: Settings,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    body: VideoRunCreate,
    requested_by: uuid.UUID,
) -> tuple[VideoRun, bool]:
    project = get_project(db, workspace_id=workspace_id, project_id=project_id)
    script = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.id == body.script_version_id,
            ScriptVersion.workspace_id == workspace_id,
            ScriptVersion.content_project_id == project.id,
            ScriptVersion.deleted_at.is_(None),
        )
    )
    if script is None:
        raise AppError(
            404, "NOT_FOUND", "Script not found", "Script version not found in this project."
        )
    provider = body.tts_provider or settings.video_tts_provider
    if (
        provider not in {"minimax", "elevenlabs", "fixture"}
        or provider != settings.video_tts_provider
    ):
        raise AppError(
            409,
            "VIDEO_TTS_NOT_CONFIGURED",
            "Video TTS is not configured",
            "Configure VIDEO_TTS_PROVIDER before requesting a video run.",
        )
    voice_id = body.voice_id
    if provider == "elevenlabs":
        voice_id = voice_id or settings.elevenlabs_voice_id
        if not voice_id:
            raise AppError(
                409,
                "ELEVENLABS_VOICE_NOT_CONFIGURED",
                "ElevenLabs voice is not configured",
                "Set ELEVENLABS_VOICE_ID or provide voice_id when requesting the video.",
            )
    request_payload = {
        "script": script.body,
        "script_version": script.version_no,
        "instruction": body.instruction,
        "render_spec": body.render_spec.model_dump(),
        "tts_provider": provider,
        "voice_id": voice_id,
    }
    digest = hashlib.sha256(
        json.dumps(request_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    dedupe_key = f"video:{project.id}:{digest}"
    if not body.force:
        existing = db.scalar(
            select(VideoRun).where(
                VideoRun.workspace_id == workspace_id,
                VideoRun.dedupe_key == dedupe_key,
                VideoRun.status.in_(("queued", "running")),
            )
        )
        if existing is not None:
            return existing, False
    if body.force:
        dedupe_key = f"{dedupe_key}:{uuid.uuid4()}"
    run = VideoRun(
        workspace_id=workspace_id,
        content_project_id=project.id,
        script_version_id=script.id,
        dedupe_key=dedupe_key,
        tts_provider=provider,
        voice_id=voice_id,
        render_spec=body.render_spec.model_dump(),
        request_payload=request_payload,
        created_by=requested_by,
    )
    db.add(run)
    db.flush()
    job, created = create_job(
        db,
        workspace_id=workspace_id,
        job_type="VIDEO_PRODUCTION",
        dedupe_key=f"video-run:{run.id}",
        payload={"video_run_id": str(run.id)},
        priority=50,
        max_attempts=2,
    )
    # A collision here is only possible after an interrupted prior transaction.
    run.sync_job_id = job.id
    if not created:
        return run, False
    db.commit()
    db.refresh(run)
    return run, True
