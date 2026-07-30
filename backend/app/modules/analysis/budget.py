import uuid
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AICostLedger, Workspace


def reserve_ai_budget(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    sync_job_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    provider: str,
    model: str,
    estimated_cost_usd: Decimal,
) -> AICostLedger:
    existing = db.scalar(select(AICostLedger).where(AICostLedger.sync_job_id == sync_job_id))
    if existing is not None:
        return existing
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
    if workspace is None:
        raise AppError(404, "NOT_FOUND", "Workspace not found", "Workspace not found.")
    if bool((workspace.settings.get("external_calls") or {}).get("paused")):
        raise AppError(
            409,
            "EXTERNAL_CALLS_PAUSED",
            "External calls are paused",
            "A workspace owner paused TikHub, AI, and ASR calls.",
        )
    usage_date = datetime.now(ZoneInfo(workspace.timezone)).date()
    effective_cost = case(
        (
            AICostLedger.status == "settled",
            func.coalesce(AICostLedger.actual_cost_usd, AICostLedger.estimated_cost_usd),
        ),
        else_=AICostLedger.estimated_cost_usd,
    )
    committed_or_reserved = db.scalar(
        select(func.coalesce(func.sum(effective_cost), 0)).where(
            AICostLedger.workspace_id == workspace.id,
            AICostLedger.usage_date == usage_date,
            AICostLedger.status.in_(("reserved", "settled", "uncertain")),
        )
    )
    if Decimal(committed_or_reserved or 0) + estimated_cost_usd > workspace.daily_ai_budget_usd:
        raise AppError(
            409,
            "ANALYSIS_BUDGET_EXCEEDED",
            "AI budget exceeded",
            "The workspace daily AI and transcription budget has been reached.",
        )
    ledger = AICostLedger(
        workspace_id=workspace.id,
        sync_job_id=sync_job_id,
        resource_type=resource_type,
        resource_id=resource_id,
        usage_date=usage_date,
        provider=provider,
        model=model,
        status="reserved",
        estimated_cost_usd=estimated_cost_usd,
    )
    db.add(ledger)
    db.flush()
    return ledger


def settle_ai_budget(
    db: Session,
    *,
    sync_job_id: uuid.UUID,
    actual_cost_usd: Decimal,
) -> None:
    ledger = db.scalar(
        select(AICostLedger).where(AICostLedger.sync_job_id == sync_job_id).with_for_update()
    )
    if ledger is None:
        raise RuntimeError("AI cost reservation is missing")
    ledger.status = "settled"
    ledger.actual_cost_usd = max(actual_cost_usd, Decimal("0"))
    ledger.settled_at = datetime.now(timezone.utc)
    db.flush()
