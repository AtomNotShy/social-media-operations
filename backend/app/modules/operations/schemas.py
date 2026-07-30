from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProviderUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usage_date: date
    provider: str
    endpoint_key: str
    request_count: int
    success_count: int
    billable_count: int
    estimated_cost_usd: Decimal


class ProviderUsageSummary(BaseModel):
    items: list[ProviderUsageRead]
    request_count: int
    success_count: int
    billable_count: int
    estimated_cost_usd: Decimal


class AIUsageSummary(BaseModel):
    run_count: int
    success_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class AIBudgetUsageSummary(BaseModel):
    ledger_count: int
    reserved_count: int
    settled_count: int
    uncertain_count: int
    reserved_cost_usd: Decimal
    settled_cost_usd: Decimal
    uncertain_cost_usd: Decimal
    effective_cost_usd: Decimal
    daily_budget_usd: Decimal


class ASRUsageSummary(BaseModel):
    transcript_count: int
    success_count: int
    audio_duration_ms: int
    cost_usd: Decimal


class QueueHealthRead(BaseModel):
    counts: dict[str, int]
    active_count: int
    oldest_active_created_at: datetime | None
    stale_running_count: int
