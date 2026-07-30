from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    level: Literal["l1", "l2"] = "l1"
    force: bool = False


class AnalysisL1Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    factors: list[str]
    confidence: float = Field(ge=0, le=1)
    caveats: list[str]
    life: Literal["timely", "evergreen"]
    life_reason: str = Field(min_length=1)
    recommended_for_l2: bool


class AnalysisL2Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hook: str
    structure: list[str]
    audience_pains: list[str]
    triggers: list[str]
    reusable_patterns: list[str]
    non_reusable_context: list[str]
    topic_ideas: list[str]
    recommended_channels: list[str]
    risks: list[str]
    fact_checks: list[str]
    evidence_refs: list[str] = Field(min_length=1)


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_content_id: UUID
    sync_job_id: UUID | None
    ai_connection_id: UUID | None
    analysis_level: str
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
    created_at: datetime
    finished_at: datetime | None


class AnalysisAccepted(BaseModel):
    analysis: AnalysisRunRead
    reused: bool


class TranscriptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_content_id: UUID
    sync_job_id: UUID | None
    provider: str
    model: str
    language: str | None
    status: str
    text: str | None
    segments: list | None
    confidence: Decimal | None
    input_hash: str
    cost_usd: Decimal
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class TranscriptAccepted(BaseModel):
    transcript: TranscriptRead
    reused: bool
