from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tracked_profiles.schemas import ExternalContentRead


class ImportURLRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    hydrate: Literal["summary", "detail"] = "detail"
    analyze: bool = False


class ImportURLRead(BaseModel):
    inspiration_id: UUID | None
    external_content_id: UUID | None
    existing: bool
    job_id: UUID | None


class InspirationUpdate(BaseModel):
    status: Literal["inbox", "analyzed", "candidate", "archived"] | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    manual_score: int | None = Field(default=None, ge=0, le=100)


class InspirationScoreSummary(BaseModel):
    grade: str
    r_value: Decimal | None
    m_value: Decimal | None
    calculated_at: datetime


class InspirationMetricSummary(BaseModel):
    captured_at: datetime
    views: int | None
    likes: int | None
    comments: int | None
    favorites: int | None
    shares: int | None


class InspirationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    source: str
    notes: str | None
    manual_score: int | None
    created_at: datetime
    updated_at: datetime
    content: ExternalContentRead
    latest_score: InspirationScoreSummary | None = None
    latest_metrics: InspirationMetricSummary | None = None


class ContentMetricSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_content_id: UUID
    captured_at: datetime
    views: int | None
    likes: int | None
    comments: int | None
    favorites: int | None
    shares: int | None
    downloads: int | None
    metrics: dict
