import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AIAttemptLog, AICostLedger, Workspace


def open_ai_attempt(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    run_type: str,
    run_id: uuid.UUID,
    sync_job_id: uuid.UUID,
    attempt_no: int,
    provider: str,
    model: str,
) -> None:
    db.add(
        AIAttemptLog(
            workspace_id=workspace_id,
            run_type=run_type,
            run_id=run_id,
            sync_job_id=sync_job_id,
            attempt_no=attempt_no,
            provider=provider,
            model=model,
            status="started",
            started_at=datetime.now(timezone.utc),
        )
    )


def close_ai_attempt(
    db: Session,
    *,
    sync_job_id: uuid.UUID,
    attempt_no: int,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: Decimal | None = None,
    latency_ms: int | None = None,
) -> None:
    attempt = db.scalar(
        select(AIAttemptLog)
        .where(
            AIAttemptLog.sync_job_id == sync_job_id,
            AIAttemptLog.attempt_no == attempt_no,
        )
        .with_for_update()
    )
    if attempt is None:
        return
    attempt.status = status
    attempt.error_code = error_code
    attempt.error_message = error_message
    attempt.input_tokens = input_tokens
    attempt.output_tokens = output_tokens
    attempt.cost_usd = cost_usd if cost_usd is not None else Decimal("0")
    attempt.latency_ms = latency_ms
    attempt.finished_at = datetime.now(timezone.utc)
    db.flush()


def estimate_generation_cost_usd(
    *,
    provider: str,
    model: str,
    input_cost_per_million_usd: Decimal,
    output_cost_per_million_usd: Decimal,
    payload: dict,
    expected_output_tokens: int = 800,
) -> Decimal:
    """Estimate a generation run's cost from the assembled context size.

    Chinese text is roughly two characters per token; using a conservative one
    character per token overestimates input tokens and keeps the reservation on
    the safe side of the workspace daily budget.
    """
    payload_chars = len(json.dumps(payload, ensure_ascii=False, default=str))
    input_tokens = max(1, payload_chars)
    input_cost = (
        Decimal(input_tokens) * input_cost_per_million_usd / Decimal(1_000_000)
    )
    output_cost = (
        Decimal(expected_output_tokens) * output_cost_per_million_usd / Decimal(1_000_000)
    )
    return (input_cost + output_cost).quantize(Decimal("0.000001"))


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
