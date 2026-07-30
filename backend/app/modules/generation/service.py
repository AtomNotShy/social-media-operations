import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    ContentProject,
    GenerationRun,
    OwnedChannel,
    PublishPlan,
    PublishRecord,
    ScriptVersion,
    Topic,
)
from app.jobs.service import create_job
from app.modules.analysis.budget import reserve_ai_budget


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _require_ai(settings: Settings) -> None:
    if settings.ai_provider == "disabled" or settings.ai_model == "disabled":
        raise AppError(
            409,
            "AI_NOT_CONFIGURED",
            "AI provider is not configured",
            "Configure an approved AI provider and model before creating generation jobs.",
        )


def _reusable_generation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    generation_type: str,
    input_hash: str,
    force: bool,
) -> GenerationRun | None:
    run = db.scalar(
        select(GenerationRun)
        .where(
            GenerationRun.workspace_id == workspace_id,
            GenerationRun.generation_type == generation_type,
            GenerationRun.input_hash == input_hash,
            GenerationRun.status.in_(("queued", "running", "succeeded")),
        )
        .limit(1)
    )
    if run is not None and force and run.status == "succeeded":
        run.status = "superseded"
        db.flush()
        return None
    return run


def _queue_generation(
    db: Session,
    *,
    run: GenerationRun,
    settings: Settings,
) -> None:
    job, _ = create_job(
        db,
        workspace_id=run.workspace_id,
        job_type="CONTENT_GENERATION",
        dedupe_key=f"generation:{run.generation_type}:{run.input_hash}",
        payload={"generation_run_id": str(run.id)},
        priority=50,
    )
    run.sync_job_id = job.id
    reserve_ai_budget(
        db,
        workspace_id=run.workspace_id,
        sync_job_id=job.id,
        resource_type="generation",
        resource_id=run.id,
        provider=run.model_provider,
        model=run.model,
        estimated_cost_usd=settings.ai_generation_estimated_cost_usd,
    )
    db.flush()


def request_script_generation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    project_version: int,
    instruction: str | None,
    force: bool,
    requested_by: uuid.UUID,
    settings: Settings,
) -> tuple[GenerationRun, bool]:
    _require_ai(settings)
    project = db.scalar(
        select(ContentProject).where(
            ContentProject.workspace_id == workspace_id,
            ContentProject.id == project_id,
            ContentProject.deleted_at.is_(None),
        )
    )
    if project is None:
        raise AppError(404, "NOT_FOUND", "Content project not found", "Project not found.")
    if project.version != project_version:
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Content project was changed",
            "Reload the latest project before generating a script.",
        )
    channel = db.scalar(
        select(OwnedChannel).where(
            OwnedChannel.workspace_id == workspace_id,
            OwnedChannel.id == project.owned_channel_id,
        )
    )
    topic = (
        db.scalar(
            select(Topic).where(
                Topic.workspace_id == workspace_id,
                Topic.id == project.topic_id,
            )
        )
        if project.topic_id is not None
        else None
    )
    latest_script = db.scalar(
        select(ScriptVersion)
        .where(
            ScriptVersion.workspace_id == workspace_id,
            ScriptVersion.content_project_id == project.id,
            ScriptVersion.deleted_at.is_(None),
        )
        .order_by(ScriptVersion.version_no.desc())
        .limit(1)
    )
    input_payload = {
        "project_id": str(project.id),
        "project_version": project.version,
        "project_title": project.title,
        "instruction": instruction,
        "topic": (
            {
                "id": str(topic.id),
                "title": topic.title,
                "audience_problem": topic.audience_problem,
                "angle": topic.angle,
                "hook": topic.hook,
                "evidence_refs": topic.evidence_refs,
            }
            if topic is not None
            else None
        ),
        "channel": (
            {
                "id": str(channel.id),
                "positioning": channel.positioning,
                "audience": channel.audience,
                "content_pillars": channel.content_pillars,
                "tone_rules": channel.tone_rules,
                "prohibited_topics": channel.prohibited_topics,
            }
            if channel is not None
            else None
        ),
        "latest_script": (
            {
                "id": str(latest_script.id),
                "version_no": latest_script.version_no,
                "body": latest_script.body,
            }
            if latest_script is not None
            else None
        ),
        "requested_by": str(requested_by),
    }
    prompt_version = f"{settings.ai_prompt_version}:script-v1"
    input_hash = _hash(
        {
            "payload": input_payload,
            "provider": settings.ai_provider,
            "model": settings.ai_model,
            "prompt_version": prompt_version,
        }
    )
    reusable = _reusable_generation(
        db,
        workspace_id=workspace_id,
        generation_type="script_draft",
        input_hash=input_hash,
        force=force,
    )
    if reusable is not None:
        return reusable, True
    evidence_refs = [f"project:{project.id}", f"channel:{project.owned_channel_id}"]
    if topic is not None:
        evidence_refs.append(f"topic:{topic.id}")
    if latest_script is not None:
        evidence_refs.append(f"script:{latest_script.id}")
    run = GenerationRun(
        workspace_id=workspace_id,
        content_project_id=project.id,
        generation_type="script_draft",
        model_provider=settings.ai_provider,
        model=settings.ai_model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        input_payload=input_payload,
        evidence_refs=evidence_refs,
    )
    db.add(run)
    db.flush()
    _queue_generation(db, run=run, settings=settings)
    return run, False


def request_review_generation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    publish_record_id: uuid.UUID,
    review_window: str,
    metrics: dict,
    primary_metric: str | None,
    force: bool,
    requested_by: uuid.UUID,
    settings: Settings,
) -> tuple[GenerationRun, bool]:
    _require_ai(settings)
    row = db.execute(
        select(PublishRecord, PublishPlan, ContentProject)
        .join(PublishPlan, PublishPlan.id == PublishRecord.publish_plan_id)
        .join(ContentProject, ContentProject.id == PublishPlan.content_project_id)
        .where(
            PublishRecord.workspace_id == workspace_id,
            PublishRecord.id == publish_record_id,
            PublishPlan.workspace_id == workspace_id,
            ContentProject.workspace_id == workspace_id,
        )
    ).one_or_none()
    if row is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Publish record not found",
            "Publish record not found.",
        )
    record, _, project = row
    input_payload = {
        "publish_record_id": str(record.id),
        "content_project_id": str(project.id),
        "published_at": record.published_at.isoformat(),
        "review_window": review_window,
        "metrics": metrics,
        "primary_metric": primary_metric,
        "requested_by": str(requested_by),
    }
    prompt_version = f"{settings.ai_prompt_version}:review-v1"
    input_hash = _hash(
        {
            "payload": input_payload,
            "provider": settings.ai_provider,
            "model": settings.ai_model,
            "prompt_version": prompt_version,
        }
    )
    reusable = _reusable_generation(
        db,
        workspace_id=workspace_id,
        generation_type="review_summary",
        input_hash=input_hash,
        force=force,
    )
    if reusable is not None:
        return reusable, True
    run = GenerationRun(
        workspace_id=workspace_id,
        content_project_id=project.id,
        publish_record_id=record.id,
        generation_type="review_summary",
        model_provider=settings.ai_provider,
        model=settings.ai_model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        input_payload=input_payload,
        evidence_refs=[f"publish_record:{record.id}", f"project:{project.id}"],
    )
    db.add(run)
    db.flush()
    _queue_generation(db, run=run, settings=settings)
    return run, False
