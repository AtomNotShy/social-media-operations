from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetricThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    views: int = Field(default=10_000, ge=0, le=10_000_000_000)
    likes: int = Field(default=200, ge=0, le=10_000_000_000)
    comments: int = Field(default=30, ge=0, le=10_000_000_000)
    favorites: int = Field(default=100, ge=0, le=10_000_000_000)
    shares: int = Field(default=50, ge=0, le=10_000_000_000)


class MetricThresholdsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    views: int | None = Field(default=None, ge=0, le=10_000_000_000)
    likes: int | None = Field(default=None, ge=0, le=10_000_000_000)
    comments: int | None = Field(default=None, ge=0, le=10_000_000_000)
    favorites: int | None = Field(default=None, ge=0, le=10_000_000_000)
    shares: int | None = Field(default=None, ge=0, le=10_000_000_000)


class AutomationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    scan_interval_hours: int = Field(default=24, ge=1, le=24 * 30)
    observation_hours: int = Field(default=72, ge=1, le=24 * 30)
    minimum_age_minutes: int = Field(default=120, ge=0, le=24 * 30 * 60)
    metric_thresholds: MetricThresholds = Field(default_factory=MetricThresholds)
    threshold_match: Literal["any", "all"] = "any"
    auto_l1: bool = True
    auto_l2: bool = True
    daily_l1_limit: int = Field(default=20, ge=0, le=10_000)
    daily_l2_limit: int = Field(default=5, ge=0, le=10_000)


class AutomationSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    scan_interval_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    observation_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    minimum_age_minutes: int | None = Field(default=None, ge=0, le=24 * 30 * 60)
    metric_thresholds: MetricThresholdsPatch | None = None
    threshold_match: Literal["any", "all"] | None = None
    auto_l1: bool | None = None
    auto_l2: bool | None = None
    daily_l1_limit: int | None = Field(default=None, ge=0, le=10_000)
    daily_l2_limit: int | None = Field(default=None, ge=0, le=10_000)


class AutomationCandidate(BaseModel):
    inspiration_id: UUID
    title: str | None
    platform: str | None
    grade: str | None
    score_mode: str | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    opportunity_score: float | None = Field(default=None, ge=0, le=100)
    content_potential_score: float | None = Field(default=None, ge=0, le=100)
    l1_status: str | None = None
    l2_status: str | None = None
    qualified_at: datetime | None = None


class AutomationToday(BaseModel):
    timezone: str
    window_start: datetime
    window_end: datetime
    scanned_profiles: int
    discovered_contents: int
    observing_contents: int
    qualified_contents: int
    l1_queued: int
    l1_completed: int
    l2_queued: int
    l2_completed: int
    estimated_cost_usd: Decimal = Decimal("0")
    actual_cost_usd: Decimal = Decimal("0")
    candidates: list[AutomationCandidate]
