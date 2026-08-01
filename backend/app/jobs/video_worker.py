"""Dedicated worker for CPU-heavy local video jobs; it never needs TikHub credentials."""

import argparse
import asyncio
import socket
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import SyncJob
from app.jobs.errors import JobExecutionError
from app.jobs.handlers.video_production import VideoProductionHandler
from app.jobs.service import claim_next_job, recover_stale_jobs, touch_process_heartbeat
from app.providers.tts.factory import build_tts_provider


async def process_one(db: Session, *, settings: Settings, worker_id: str) -> bool:
    recover_stale_jobs(db, lock_timeout_seconds=settings.job_lock_timeout_seconds)
    db.commit()
    job = claim_next_job(db, worker_id, job_types=("VIDEO_PRODUCTION",))
    if job is None:
        touch_process_heartbeat(db, instance_id=worker_id, service="video-worker")
        db.commit()
        return False
    touch_process_heartbeat(
        db, instance_id=worker_id, service="video-worker", current_job_id=job.id
    )
    db.commit()
    try:
        result = await VideoProductionHandler(
            db, settings=settings, tts_provider=build_tts_provider(settings)
        ).handle(job)
        current = db.get(SyncJob, job.id)
        if current is not None:
            current.status, current.result = "succeeded", result
            current.finished_at = datetime.now(timezone.utc)
            current.locked_at = current.locked_by = current.heartbeat_at = None
            touch_process_heartbeat(db, instance_id=worker_id, service="video-worker")
            db.commit()
        return True
    except JobExecutionError as exc:
        db.rollback()
        current = db.get(SyncJob, job.id)
        if current is not None:
            current.last_error_code, current.last_error_message = exc.code, exc.message
            current.locked_at = current.locked_by = current.heartbeat_at = None
            if exc.retryable and current.attempt < current.max_attempts:
                current.status = "retry_wait"
                current.run_after = datetime.now(timezone.utc) + timedelta(seconds=60)
            else:
                current.status, current.finished_at = "dead", datetime.now(timezone.utc)
            touch_process_heartbeat(db, instance_id=worker_id, service="video-worker")
            db.commit()
        return True


async def run_worker(settings: Settings, *, once: bool = False) -> None:
    from app.db.session import Database

    database = Database(settings.database_url)
    worker_id = f"video:{socket.gethostname()}:{id(asyncio.current_task())}"
    try:
        while True:
            with database.session_factory() as db:
                processed = await process_one(db, settings=settings, worker_id=worker_id)
            if once:
                return
            if not processed:
                await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local video production worker")
    parser.add_argument("--once", action="store_true", help="Process at most one video job")
    args = parser.parse_args()
    asyncio.run(run_worker(get_settings(), once=args.once))


if __name__ == "__main__":
    main()
