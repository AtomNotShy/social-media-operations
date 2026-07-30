from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScriptGenerateRequest(BaseModel):
    project_version: int = Field(ge=1)
    instruction: str | None = Field(default=None, max_length=10000)
    force: bool = False


class ReviewGenerateRequest(BaseModel):
    review_window: str = Field(pattern=r"^(24h|7d|30d|manual)$")
    metrics: dict
    primary_metric: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_.-]{1,64}$",
    )
    force: bool = False


class GeneratedScriptResult(BaseModel):
    body: str = Field(min_length=1, max_length=100000)
    structured_body: dict | None = None
    rationale: str = Field(min_length=1, max_length=10000)
    evidence_refs: list[str] = Field(min_length=1, max_length=100)


class GeneratedReviewResult(BaseModel):
    analysis: dict
    next_actions: list[str] = Field(max_length=100)
    evidence_refs: list[str] = Field(min_length=1, max_length=100)


class GenerationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_project_id: UUID
    publish_record_id: UUID | None
    sync_job_id: UUID | None
    ai_connection_id: UUID | None
    generation_type: str
    model_provider: str
    model: str
    prompt_version: str
    input_hash: str
    status: str
    result: dict | None
    evidence_refs: list
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal
    latency_ms: int | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class GenerationAccepted(BaseModel):
    generation: GenerationRunRead
    reused: bool
