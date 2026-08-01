import argparse
import asyncio
import socket
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import SyncJob
from app.db.session import Database
from app.jobs.errors import JobExecutionError
from app.jobs.handlers.analysis import AnalysisHandler
from app.jobs.handlers.comments import CommentFetchHandler
from app.jobs.handlers.content_detail import ContentDetailHandler
from app.jobs.handlers.discovery import DiscoverySearchHandler
from app.jobs.handlers.generation import GenerationHandler
from app.jobs.handlers.profile_scan import ProfileScanHandler
from app.jobs.handlers.transcript import TranscriptHandler
from app.jobs.service import claim_next_job, recover_stale_jobs, touch_process_heartbeat
from app.providers.ai.base import AnalysisProvider
from app.providers.ai.fixture import FixtureAnalysisProvider
from app.providers.ai.generation import (
    ContentGenerationProvider,
    FixtureContentGenerationProvider,
)
from app.providers.asr.base import TranscriptProvider
from app.providers.asr.fixture import FixtureTranscriptProvider
from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway


async def process_one(
    db: Session,
    *,
    client: TikHubHttpClient,
    worker_id: str,
    lock_timeout_seconds: int = 300,
    analysis_provider: AnalysisProvider | None = None,
    generation_provider: ContentGenerationProvider | None = None,
    transcript_provider: TranscriptProvider | None = None,
    circuit_failure_threshold: int = 5,
    circuit_open_seconds: int = 300,
    settings: Settings | None = None,
) -> bool:
    recover_stale_jobs(db, lock_timeout_seconds=lock_timeout_seconds)
    db.commit()
    job = claim_next_job(
        db,
        worker_id,
        job_types=(
            "PROFILE_SCAN",
            "CONTENT_DETAIL_FETCH",
            "AI_ANALYSIS",
            "TRANSCRIBE",
            "CONTENT_GENERATION",
            "COMMENT_FETCH",
            "DISCOVERY_SEARCH",
        ),
    )
    if job is None:
        touch_process_heartbeat(
            db,
            instance_id=worker_id,
            service="worker",
        )
        db.commit()
        return False
    touch_process_heartbeat(
        db,
        instance_id=worker_id,
        service="worker",
        current_job_id=job.id,
    )
    db.commit()
    try:
        if job.job_type == "PROFILE_SCAN":
            handler = ProfileScanHandler(
                db,
                TikHubGateway(
                    db,
                    client,
                    circuit_failure_threshold=circuit_failure_threshold,
                    circuit_open_seconds=circuit_open_seconds,
                ),
                settings=settings,
            )
        elif job.job_type == "CONTENT_DETAIL_FETCH":
            handler = ContentDetailHandler(
                db,
                TikHubGateway(
                    db,
                    client,
                    circuit_failure_threshold=circuit_failure_threshold,
                    circuit_open_seconds=circuit_open_seconds,
                ),
                settings=settings,
            )
        elif job.job_type == "AI_ANALYSIS":
            handler = AnalysisHandler(db, analysis_provider, settings=settings)
        elif job.job_type == "TRANSCRIBE":
            handler = TranscriptHandler(db, transcript_provider)
        elif job.job_type == "CONTENT_GENERATION":
            handler = GenerationHandler(db, generation_provider, settings=settings)
        elif job.job_type == "COMMENT_FETCH":
            handler = CommentFetchHandler(
                db,
                TikHubGateway(
                    db,
                    client,
                    circuit_failure_threshold=circuit_failure_threshold,
                    circuit_open_seconds=circuit_open_seconds,
                ),
            )
        elif job.job_type == "DISCOVERY_SEARCH":
            handler = DiscoverySearchHandler(
                db,
                TikHubGateway(
                    db,
                    client,
                    circuit_failure_threshold=circuit_failure_threshold,
                    circuit_open_seconds=circuit_open_seconds,
                ),
            )
        else:
            raise TikHubError(
                code="JOB_TYPE_UNSUPPORTED",
                message=f"No handler is registered for {job.job_type}.",
                retryable=False,
            )
        result = await handler.handle(job)
        current_job = db.get(SyncJob, job.id)
        if current_job is not None:
            current_job.status = "succeeded"
            current_job.result = result
            current_job.finished_at = datetime.now(timezone.utc)
            current_job.locked_at = None
            current_job.locked_by = None
            current_job.heartbeat_at = None
            touch_process_heartbeat(
                db,
                instance_id=worker_id,
                service="worker",
            )
            db.commit()
        return True
    except (TikHubError, JobExecutionError) as exc:
        db.rollback()
        current_job = db.get(SyncJob, job.id)
        if current_job is not None:
            current_job.last_error_code = exc.code
            current_job.last_error_message = exc.message
            current_job.locked_at = None
            current_job.locked_by = None
            current_job.heartbeat_at = None
            if exc.retryable and current_job.attempt < current_job.max_attempts:
                current_job.status = "retry_wait"
                current_job.run_after = datetime.now(timezone.utc) + timedelta(
                    seconds=min(60 * (2 ** (current_job.attempt - 1)), 3600)
                )
            else:
                current_job.status = "dead"
                current_job.finished_at = datetime.now(timezone.utc)
            touch_process_heartbeat(
                db,
                instance_id=worker_id,
                service="worker",
            )
            db.commit()
        return True
    except Exception:
        db.rollback()
        current_job = db.get(SyncJob, job.id)
        if current_job is not None:
            current_job.status = "dead"
            current_job.last_error_code = "INTERNAL_JOB_ERROR"
            current_job.last_error_message = "The job failed during normalization or persistence."
            current_job.finished_at = datetime.now(timezone.utc)
            current_job.locked_at = None
            current_job.locked_by = None
            current_job.heartbeat_at = None
            touch_process_heartbeat(
                db,
                instance_id=worker_id,
                service="worker",
            )
            db.commit()
        return True


async def run_worker(settings: Settings, *, once: bool = False) -> None:
    if not settings.tikhub_api_key:
        raise RuntimeError("TIKHUB_API_KEY is required to run the worker")
    database = Database(settings.database_url)
    async with httpx.AsyncClient(
        base_url=settings.tikhub_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {settings.tikhub_api_key.strip()}",
            "Accept": "application/json",
            "User-Agent": "social-ops-backend/0.1",
        },
        follow_redirects=False,
    ) as http_client:
        client = TikHubHttpClient(
            base_url=settings.tikhub_base_url,
            api_key=settings.tikhub_api_key,
            client=http_client,
        )
        analysis_provider = FixtureAnalysisProvider() if settings.ai_provider == "fixture" else None
        generation_provider = (
            FixtureContentGenerationProvider() if settings.ai_provider == "fixture" else None
        )
        transcript_provider = (
            FixtureTranscriptProvider() if settings.asr_provider == "fixture" else None
        )
        worker_id = f"{socket.gethostname()}:{id(asyncio.current_task())}"
        try:
            while True:
                with database.session_factory() as db:
                    processed = await process_one(
                        db,
                        client=client,
                        worker_id=worker_id,
                        lock_timeout_seconds=settings.job_lock_timeout_seconds,
                        analysis_provider=analysis_provider,
                        generation_provider=generation_provider,
                        transcript_provider=transcript_provider,
                        circuit_failure_threshold=settings.provider_circuit_failure_threshold,
                        circuit_open_seconds=settings.provider_circuit_open_seconds,
                        settings=settings,
                    )
                if once:
                    return
                if not processed:
                    await asyncio.sleep(settings.worker_poll_seconds)
        finally:
            database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the social-ops job worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job")
    args = parser.parse_args()
    asyncio.run(run_worker(get_settings(), once=args.once))


if __name__ == "__main__":
    main()
