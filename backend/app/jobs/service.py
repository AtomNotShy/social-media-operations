import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ACTIVE_JOB_STATUSES, ProcessHeartbeat, SyncJob, TrackedProfile


def touch_process_heartbeat(
    db: Session,
    *,
    instance_id: str,
    service: str,
    current_job_id: uuid.UUID | None = None,
) -> ProcessHeartbeat:
    now = datetime.now(timezone.utc)
    heartbeat = db.scalar(
        select(ProcessHeartbeat)
        .where(ProcessHeartbeat.instance_id == instance_id)
        .with_for_update()
    )
    if heartbeat is None:
        heartbeat = ProcessHeartbeat(
            instance_id=instance_id,
            service=service,
            started_at=now,
            heartbeat_at=now,
            current_job_id=current_job_id,
        )
        db.add(heartbeat)
    else:
        heartbeat.service = service
        heartbeat.heartbeat_at = now
        heartbeat.current_job_id = current_job_id
    db.flush()
    return heartbeat


def create_job(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    job_type: str,
    dedupe_key: str,
    payload: dict,
    priority: int = 50,
    max_attempts: int = 3,
) -> tuple[SyncJob, bool]:
    job = SyncJob(
        workspace_id=workspace_id,
        job_type=job_type,
        dedupe_key=dedupe_key,
        payload=payload,
        priority=priority,
        max_attempts=max_attempts,
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
        return job, True
    except IntegrityError:
        existing = db.scalar(
            select(SyncJob).where(
                SyncJob.workspace_id == workspace_id,
                SyncJob.dedupe_key == dedupe_key,
                SyncJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        if existing is None:
            raise
        return existing, False


def claim_next_job(db: Session, worker_id: str) -> SyncJob | None:
    now = datetime.now(timezone.utc)
    query: Select[tuple[SyncJob]] = (
        select(SyncJob)
        .where(
            SyncJob.status.in_(("pending", "retry_wait")),
            SyncJob.run_after <= now,
        )
        .order_by(SyncJob.priority.desc(), SyncJob.run_after, SyncJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.scalar(query)
    if job is None:
        return None
    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = now
    job.heartbeat_at = now
    job.attempt += 1
    db.flush()
    return job


def recover_stale_jobs(
    db: Session,
    *,
    lock_timeout_seconds: int,
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=lock_timeout_seconds)
    jobs = db.scalars(
        select(SyncJob)
        .where(
            SyncJob.status == "running",
            or_(
                SyncJob.heartbeat_at < cutoff,
                SyncJob.heartbeat_at.is_(None) & (SyncJob.locked_at < cutoff),
            ),
        )
        .with_for_update(skip_locked=True)
    ).all()
    recovered = 0
    dead = 0
    for job in jobs:
        job.locked_at = None
        job.locked_by = None
        job.heartbeat_at = None
        job.last_error_code = "STALE_JOB_RECOVERED"
        job.last_error_message = "The worker lock expired before the job finished."
        if job.attempt >= job.max_attempts:
            job.status = "dead"
            job.finished_at = now
            dead += 1
        else:
            job.status = "retry_wait"
            job.run_after = now
            job.finished_at = None
            recovered += 1
    db.flush()
    return recovered, dead


def schedule_due_profile_scans(
    db: Session,
    *,
    limit: int = 100,
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    profiles = db.scalars(
        select(TrackedProfile)
        .where(
            TrackedProfile.active.is_(True),
            TrackedProfile.sync_status == "idle",
            TrackedProfile.next_scan_at.is_not(None),
            TrackedProfile.next_scan_at <= now,
        )
        .order_by(TrackedProfile.priority.desc(), TrackedProfile.next_scan_at)
        .with_for_update(skip_locked=True)
        .limit(limit)
    ).all()
    created = 0
    deduplicated = 0
    for profile in profiles:
        _, was_created = create_job(
            db,
            workspace_id=profile.workspace_id,
            job_type="PROFILE_SCAN",
            dedupe_key=f"profile-sync:{profile.id}",
            payload={"tracked_profile_id": str(profile.id), "source": "scheduler"},
            priority=profile.priority,
        )
        if was_created:
            created += 1
        else:
            deduplicated += 1
    db.flush()
    return created, deduplicated


def queue_counts(db: Session, *, workspace_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(SyncJob.status, func.count(SyncJob.id))
        .where(SyncJob.workspace_id == workspace_id)
        .group_by(SyncJob.status)
    ).all()
    return {status: count for status, count in rows}
