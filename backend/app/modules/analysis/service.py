import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    AnalysisRun,
    ContentScore,
    ExternalContent,
    Transcript,
    WorkspaceInspiration,
)
from app.jobs.service import create_job
from app.modules.ai_connections.service import resolve_route
from app.modules.analysis.budget import reserve_ai_budget

ANALYSIS_PROMPT_LOCALE_REVISION = "zh-cn-v1"


def inspiration_content(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    inspiration_id: uuid.UUID,
) -> ExternalContent:
    content = db.scalar(
        select(ExternalContent)
        .join(
            WorkspaceInspiration,
            WorkspaceInspiration.external_content_id == ExternalContent.id,
        )
        .where(
            WorkspaceInspiration.workspace_id == workspace_id,
            WorkspaceInspiration.id == inspiration_id,
            ExternalContent.workspace_id == workspace_id,
        )
    )
    if content is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Inspiration not found",
            "Inspiration not found.",
        )
    return content


def _hash(material: dict) -> str:
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _content_version(content: ExternalContent) -> str:
    return content.content_hash or _hash(
        {
            "id": str(content.id),
            "latest_provider_fetch_id": (
                str(content.latest_provider_fetch_id)
                if content.latest_provider_fetch_id is not None
                else None
            ),
            "updated_at": content.updated_at.isoformat(),
        }
    )


def _latest_succeeded_transcript(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    content_id: uuid.UUID,
) -> Transcript | None:
    return db.scalar(
        select(Transcript)
        .where(
            Transcript.workspace_id == workspace_id,
            Transcript.external_content_id == content_id,
            Transcript.status == "succeeded",
        )
        .order_by(Transcript.finished_at.desc(), Transcript.created_at.desc())
        .limit(1)
    )


def _enforce_l2_gate(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    content_id: uuid.UUID,
) -> None:
    score = db.scalar(
        select(ContentScore)
        .where(
            ContentScore.workspace_id == workspace_id,
            ContentScore.external_content_id == content_id,
        )
        .order_by(ContentScore.calculated_at.desc(), ContentScore.id.desc())
        .limit(1)
    )
    l1 = db.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.workspace_id == workspace_id,
            AnalysisRun.external_content_id == content_id,
            AnalysisRun.analysis_level == "l1",
            AnalysisRun.status == "succeeded",
        )
        .order_by(AnalysisRun.finished_at.desc(), AnalysisRun.created_at.desc())
        .limit(1)
    )
    if score is None or score.grade not in {"t1", "t2"}:
        raise AppError(
            409,
            "L2_POLICY_REJECTED",
            "Content is not eligible for L2",
            "L2 requires the latest score to be T1 or T2.",
        )
    if l1 is None or not bool((l1.result or {}).get("recommended_for_l2")):
        raise AppError(
            409,
            "L2_POLICY_REJECTED",
            "Content is not eligible for L2",
            "L2 requires a successful L1 run that recommends deeper analysis.",
        )


def request_analysis(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    inspiration_id: uuid.UUID,
    level: str,
    force: bool,
    settings: Settings,
) -> tuple[AnalysisRun, bool]:
    route = resolve_route(
        db,
        workspace_id=workspace_id,
        task_type=level,
        settings=settings,
        include_secret=False,
    )
    content = inspiration_content(
        db,
        workspace_id=workspace_id,
        inspiration_id=inspiration_id,
    )
    if level == "l2":
        _enforce_l2_gate(
            db,
            workspace_id=workspace_id,
            content_id=content.id,
        )
    transcript = _latest_succeeded_transcript(
        db,
        workspace_id=workspace_id,
        content_id=content.id,
    )
    prompt_version = (
        f"{settings.ai_prompt_version}:{ANALYSIS_PROMPT_LOCALE_REVISION}"
        if level == "l1"
        else f"{settings.ai_prompt_version}:l2:{ANALYSIS_PROMPT_LOCALE_REVISION}"
    )
    input_hash = _hash(
        {
            "content_version": _content_version(content),
            "transcript_version": transcript.input_hash if transcript is not None else None,
            "prompt_version": prompt_version,
            "model_provider": route.provider,
            "model": route.model,
            "ai_connection_id": str(route.connection_id) if route.connection_id else None,
            "analysis_level": level,
        }
    )
    reusable = db.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.workspace_id == workspace_id,
            AnalysisRun.analysis_level == level,
            AnalysisRun.input_hash == input_hash,
            AnalysisRun.status.in_(("queued", "running", "succeeded")),
        )
        .limit(1)
    )
    if reusable is not None and (not force or reusable.status in {"queued", "running"}):
        return reusable, True
    if reusable is not None:
        reusable.status = "superseded"
        db.flush()

    run = AnalysisRun(
        workspace_id=workspace_id,
        external_content_id=content.id,
        ai_connection_id=route.connection_id,
        analysis_level=level,
        model_provider=route.provider,
        model=route.model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        status="queued",
        evidence_refs=[f"content:{content.id}"],
    )
    db.add(run)
    db.flush()
    job, _ = create_job(
        db,
        workspace_id=workspace_id,
        job_type="AI_ANALYSIS",
        dedupe_key=f"analysis:{level}:{input_hash}",
        payload={"analysis_run_id": str(run.id)},
        priority=60 if level == "l1" else 50,
    )
    run.sync_job_id = job.id
    estimated_cost = (
        settings.ai_l1_estimated_cost_usd if level == "l1" else settings.ai_l2_estimated_cost_usd
    )
    reserve_ai_budget(
        db,
        workspace_id=workspace_id,
        sync_job_id=job.id,
        resource_type="analysis",
        resource_id=run.id,
        provider=route.provider,
        model=route.model,
        estimated_cost_usd=estimated_cost,
    )
    db.flush()
    return run, False


def request_transcript(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    inspiration_id: uuid.UUID,
    settings: Settings,
) -> tuple[Transcript, bool]:
    if settings.asr_provider == "disabled" or settings.asr_model == "disabled":
        raise AppError(
            409,
            "ASR_NOT_CONFIGURED",
            "Transcription provider is not configured",
            "Configure an approved ASR provider and model before creating transcript jobs.",
        )
    content = inspiration_content(
        db,
        workspace_id=workspace_id,
        inspiration_id=inspiration_id,
    )
    media_urls = [
        item.get("url")
        for item in content.media_manifest
        if isinstance(item, dict) and item.get("type") == "video" and item.get("url")
    ]
    if not media_urls:
        raise AppError(
            409,
            "TRANSCRIPT_SOURCE_MISSING",
            "No transcribable media",
            "Hydrate a video source before requesting transcription.",
        )
    input_hash = _hash(
        {
            "content_version": _content_version(content),
            "media_urls": media_urls,
            "provider": settings.asr_provider,
            "model": settings.asr_model,
        }
    )
    existing = db.scalar(
        select(Transcript).where(
            Transcript.workspace_id == workspace_id,
            Transcript.external_content_id == content.id,
            Transcript.input_hash == input_hash,
            Transcript.provider == settings.asr_provider,
            Transcript.model == settings.asr_model,
        )
    )
    if existing is not None:
        return existing, True
    transcript = Transcript(
        workspace_id=workspace_id,
        external_content_id=content.id,
        provider=settings.asr_provider,
        model=settings.asr_model,
        status="queued",
        input_hash=input_hash,
    )
    db.add(transcript)
    db.flush()
    job, _ = create_job(
        db,
        workspace_id=workspace_id,
        job_type="TRANSCRIBE",
        dedupe_key=f"transcript:{input_hash}",
        payload={"transcript_id": str(transcript.id)},
        priority=55,
    )
    transcript.sync_job_id = job.id
    reserve_ai_budget(
        db,
        workspace_id=workspace_id,
        sync_job_id=job.id,
        resource_type="transcript",
        resource_id=transcript.id,
        provider=settings.asr_provider,
        model=settings.asr_model,
        estimated_cost_usd=settings.asr_estimated_cost_usd,
    )
    db.flush()
    return transcript, False
