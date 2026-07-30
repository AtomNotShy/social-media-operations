from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.db.models import SyncJob, TrackedProfile
from app.jobs.service import recover_stale_jobs, schedule_due_profile_scans


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _create_profile(client, headers, external_id):
    response = client.post(
        "/api/v1/tracked-profiles",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "external_id": external_id,
            "profile_url": f"https://www.xiaohongshu.com/user/profile/{external_id}",
            "display_name": external_id,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_stale_jobs_are_recovered_or_exhausted(app, workspace):
    workspace_id = UUID(workspace["id"])
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    with app.state.database.session_factory() as db:
        retryable = SyncJob(
            workspace_id=workspace_id,
            job_type="PROFILE_SCAN",
            dedupe_key="stale-retryable",
            payload={},
            status="running",
            attempt=1,
            max_attempts=3,
            locked_at=stale_at,
            heartbeat_at=stale_at,
        )
        exhausted = SyncJob(
            workspace_id=workspace_id,
            job_type="PROFILE_SCAN",
            dedupe_key="stale-exhausted",
            payload={},
            status="running",
            attempt=3,
            max_attempts=3,
            locked_at=stale_at,
            heartbeat_at=stale_at,
        )
        db.add_all([retryable, exhausted])
        db.commit()
        retryable_id = retryable.id
        exhausted_id = exhausted.id

    with app.state.database.session_factory() as db:
        recovered, dead = recover_stale_jobs(db, lock_timeout_seconds=300)
        db.commit()
        assert (recovered, dead) == (1, 1)

        retryable = db.get(SyncJob, retryable_id)
        exhausted = db.get(SyncJob, exhausted_id)
        assert retryable.status == "retry_wait"
        assert retryable.locked_by is None
        assert retryable.last_error_code == "STALE_JOB_RECOVERED"
        assert exhausted.status == "dead"
        assert exhausted.finished_at is not None


def test_scheduler_only_enqueues_due_idle_profiles(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    due = _create_profile(client, headers, "due")
    not_due = _create_profile(client, headers, "not-due")
    paused = _create_profile(client, headers, "paused")
    assert (
        client.post(
            f"/api/v1/tracked-profiles/{paused['id']}/pause",
            headers=headers,
        ).status_code
        == 200
    )

    with app.state.database.session_factory() as db:
        future_profile = db.get(TrackedProfile, UUID(not_due["id"]))
        future_profile.next_scan_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()

    with app.state.database.session_factory() as db:
        created, deduplicated = schedule_due_profile_scans(db)
        db.commit()
        assert (created, deduplicated) == (1, 0)
        jobs = db.scalars(select(SyncJob)).all()
        assert len(jobs) == 1
        assert jobs[0].payload["tracked_profile_id"] == due["id"]

    with app.state.database.session_factory() as db:
        created, deduplicated = schedule_due_profile_scans(db)
        db.commit()
        assert (created, deduplicated) == (0, 1)
        assert len(db.scalars(select(SyncJob)).all()) == 1
