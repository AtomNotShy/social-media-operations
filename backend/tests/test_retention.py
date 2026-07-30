from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.models import ExternalContent, ProviderFetch
from app.modules.operations.retention import redact_expired_provider_payloads


def _provider_fetch(workspace_id, *, fingerprint, fetched_at, error_code=None):
    return ProviderFetch(
        workspace_id=workspace_id,
        provider="tikhub",
        platform="xiaohongshu",
        endpoint_key="fixture",
        endpoint_path="/fixture",
        endpoint_version="test",
        request_fingerprint=fingerprint,
        request_params_redacted={},
        billable=error_code is None,
        estimated_cost_usd=Decimal("0.001") if error_code is None else Decimal("0"),
        response_payload={"data": "sensitive-provider-payload"},
        fetched_at=fetched_at,
        error_code=error_code,
    )


def test_retention_dry_run_and_evidence_preservation(app, workspace):
    now = datetime.now(timezone.utc)
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        unreferenced = _provider_fetch(
            workspace_id,
            fingerprint="unreferenced",
            fetched_at=now - timedelta(days=100),
        )
        referenced = _provider_fetch(
            workspace_id,
            fingerprint="referenced",
            fetched_at=now - timedelta(days=100),
        )
        failed = _provider_fetch(
            workspace_id,
            fingerprint="failed",
            fetched_at=now - timedelta(days=40),
            error_code="PROVIDER_ERROR",
        )
        db.add_all([unreferenced, referenced, failed])
        db.flush()
        db.add(
            ExternalContent(
                workspace_id=workspace_id,
                platform="xiaohongshu",
                external_id="retained-evidence",
                canonical_url="https://www.xiaohongshu.com/explore/retained-evidence",
                content_type="image_text",
                author_snapshot={},
                media_manifest=[],
                latest_provider_fetch_id=referenced.id,
            )
        )
        db.commit()

        dry_run = redact_expired_provider_payloads(
            db,
            successful_retention_days=90,
            failed_retention_days=30,
            execute=False,
            now=now,
        )
        assert dry_run.eligible_payloads == 2
        assert dry_run.redacted_payloads == 0

        executed = redact_expired_provider_payloads(
            db,
            successful_retention_days=90,
            failed_retention_days=30,
            execute=True,
            now=now,
        )
        assert executed.redacted_payloads == 2
        payloads = {
            item.request_fingerprint: item.response_payload
            for item in db.scalars(select(ProviderFetch)).all()
        }
        assert payloads == {
            "unreferenced": None,
            "referenced": {"data": "sensitive-provider-payload"},
            "failed": None,
        }
