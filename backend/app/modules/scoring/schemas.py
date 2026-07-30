from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScoringPolicyCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    core_metric_formula: dict
    tier_thresholds: dict
    grade_thresholds: dict
    minimum_age_minutes: int = Field(default=60, ge=0, le=43200)
    minimum_baseline_count: int = Field(default=5, ge=1, le=20)


class ScoringPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    version: int
    core_metric_formula: dict
    tier_thresholds: dict
    grade_thresholds: dict
    minimum_age_minutes: int
    minimum_baseline_count: int
    active: bool
    created_at: datetime


class ContentScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_content_id: UUID
    scoring_policy_id: UUID
    calculated_at: datetime
    r_value: Decimal | None
    m_value: Decimal | None
    tier: str | None
    grade: str
    core_metric: Decimal | None
    baseline_value: Decimal | None
    is_initial: bool
    evidence: dict
