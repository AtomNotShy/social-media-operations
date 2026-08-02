import hashlib
import json
import uuid
from decimal import Decimal

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
from app.modules.ai_connections.service import ResolvedAIRoute, resolve_route
from app.modules.analysis.budget import (
    estimate_generation_cost_usd,
    reserve_ai_budget,
)
from app.modules.content_packages.schemas import CONTENT_PACKAGE_SCHEMA_VERSION
from app.modules.generation.evidence import (
    EVIDENCE_CONTEXT_VERSION,
    MAX_EVIDENCE_BODY_CHARS,
    resolve_topic_evidence,
)
from app.modules.prompts.registry import (
    CONTENT_PACKAGE_PROMPT_REVISION,
    REVIEW_GENERATION_PROMPT_REVISION,
    SCRIPT_GENERATION_PROMPT_REVISION,
)


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _require_ai(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    settings: Settings,
) -> ResolvedAIRoute:
    return resolve_route(
        db,
        workspace_id=workspace_id,
        task_type="generation",
        settings=settings,
        include_secret=False,
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
    estimated_cost_usd: Decimal,
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
        estimated_cost_usd=estimated_cost_usd,
    )
    db.flush()


def _trim(value: str | None, limit: int = MAX_EVIDENCE_BODY_CHARS) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[:limit]}\n[truncated]"


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
    route = _require_ai(db, workspace_id=workspace_id, settings=settings)
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
    source_materials = resolve_topic_evidence(
        db,
        workspace_id=workspace_id,
        evidence_refs=topic.evidence_refs if topic is not None else [],
    )
    input_payload = {
        "project_id": str(project.id),
        "project_version": project.version,
        "project_title": project.title,
        "instruction": instruction,
        "source_materials": source_materials,
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
    prompt_version = f"{settings.ai_prompt_version}:{SCRIPT_GENERATION_PROMPT_REVISION}"
    input_hash = _hash(
        {
            "payload": input_payload,
            "provider": route.provider,
            "model": route.model,
            "ai_connection_id": str(route.connection_id) if route.connection_id else None,
            "prompt_version": prompt_version,
            "evidence_context": EVIDENCE_CONTEXT_VERSION,
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
    for unit in source_materials:
        evidence_refs.append(unit["ref"])
    if latest_script is not None:
        evidence_refs.append(f"script:{latest_script.id}")
    run = GenerationRun(
        workspace_id=workspace_id,
        content_project_id=project.id,
        ai_connection_id=route.connection_id,
        generation_type="script_draft",
        model_provider=route.provider,
        model=route.model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        input_payload=input_payload,
        evidence_refs=evidence_refs,
    )
    db.add(run)
    db.flush()
    _queue_generation(
        db,
        run=run,
        settings=settings,
        estimated_cost_usd=estimate_generation_cost_usd(
            provider=route.provider,
            model=route.model,
            input_cost_per_million_usd=route.input_cost_per_million_usd,
            output_cost_per_million_usd=route.output_cost_per_million_usd,
            payload=input_payload,
        ),
    )
    return run, False


def request_content_package_generation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    project_version: int,
    script_version_id: uuid.UUID,
    target_platform: str,
    force: bool,
    requested_by: uuid.UUID,
    settings: Settings,
) -> tuple[GenerationRun, bool]:
    route = _require_ai(db, workspace_id=workspace_id, settings=settings)
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
            "Reload the latest project before generating a content package.",
        )
    script = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.workspace_id == workspace_id,
            ScriptVersion.content_project_id == project.id,
            ScriptVersion.id == script_version_id,
            ScriptVersion.deleted_at.is_(None),
        )
    )
    if script is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Script version not found",
            "The selected script version does not belong to this project.",
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
    input_payload = {
        "project_id": str(project.id),
        "project_version": project.version,
        "project_title": project.title,
        "target_platform": target_platform,
        "script": {
            "id": str(script.id),
            "version_no": script.version_no,
            "body": script.body,
            "structured_body": script.structured_body or {},
        },
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
                "platform": channel.platform,
                "positioning": channel.positioning,
                "audience": channel.audience,
                "content_pillars": channel.content_pillars,
                "tone_rules": channel.tone_rules,
                "prohibited_topics": channel.prohibited_topics,
            }
            if channel is not None
            else None
        ),
        "requested_by": str(requested_by),
    }
    prompt_version = f"{settings.ai_prompt_version}:{CONTENT_PACKAGE_PROMPT_REVISION}"
    input_hash = _hash(
        {
            "payload": input_payload,
            "provider": route.provider,
            "model": route.model,
            "ai_connection_id": str(route.connection_id) if route.connection_id else None,
            "prompt_version": prompt_version,
            "evidence_context": EVIDENCE_CONTEXT_VERSION,
            "package_schema_version": CONTENT_PACKAGE_SCHEMA_VERSION,
        }
    )
    reusable = _reusable_generation(
        db,
        workspace_id=workspace_id,
        generation_type="content_package",
        input_hash=input_hash,
        force=force,
    )
    if reusable is not None:
        return reusable, True
    evidence_refs = [f"project:{project.id}", f"channel:{project.owned_channel_id}"]
    if topic is not None:
        evidence_refs.append(f"topic:{topic.id}")
    evidence_refs.append(f"script:{script.id}")
    run = GenerationRun(
        workspace_id=workspace_id,
        content_project_id=project.id,
        ai_connection_id=route.connection_id,
        generation_type="content_package",
        model_provider=route.provider,
        model=route.model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        input_payload=input_payload,
        evidence_refs=evidence_refs,
    )
    db.add(run)
    db.flush()
    _queue_generation(
        db,
        run=run,
        settings=settings,
        estimated_cost_usd=estimate_generation_cost_usd(
            provider=route.provider,
            model=route.model,
            input_cost_per_million_usd=route.input_cost_per_million_usd,
            output_cost_per_million_usd=route.output_cost_per_million_usd,
            payload=input_payload,
        ),
    )
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
    route = _require_ai(db, workspace_id=workspace_id, settings=settings)
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
    record, plan, project = row
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
        "publish_record_id": str(record.id),
        "content_project_id": str(project.id),
        "published_at": record.published_at.isoformat(),
        "review_window": review_window,
        "metrics": metrics,
        "primary_metric": primary_metric,
        "publish_payload": plan.publish_payload or {},
        "script": (
            {
                "id": str(latest_script.id),
                "version_no": latest_script.version_no,
                "body": _trim(latest_script.body),
            }
            if latest_script is not None
            else None
        ),
        "requested_by": str(requested_by),
    }
    prompt_version = f"{settings.ai_prompt_version}:{REVIEW_GENERATION_PROMPT_REVISION}"
    input_hash = _hash(
        {
            "payload": input_payload,
            "provider": route.provider,
            "model": route.model,
            "ai_connection_id": str(route.connection_id) if route.connection_id else None,
            "prompt_version": prompt_version,
            "evidence_context": EVIDENCE_CONTEXT_VERSION,
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
    evidence_refs = [f"publish_record:{record.id}", f"project:{project.id}"]
    if latest_script is not None:
        evidence_refs.append(f"script:{latest_script.id}")
    run = GenerationRun(
        workspace_id=workspace_id,
        content_project_id=project.id,
        publish_record_id=record.id,
        ai_connection_id=route.connection_id,
        generation_type="review_summary",
        model_provider=route.provider,
        model=route.model,
        prompt_version=prompt_version,
        input_hash=input_hash,
        input_payload=input_payload,
        evidence_refs=evidence_refs,
    )
    db.add(run)
    db.flush()
    _queue_generation(
        db,
        run=run,
        settings=settings,
        estimated_cost_usd=estimate_generation_cost_usd(
            provider=route.provider,
            model=route.model,
            input_cost_per_million_usd=route.input_cost_per_million_usd,
            output_cost_per_million_usd=route.output_cost_per_million_usd,
            payload=input_payload,
        ),
    )
    return run, False
