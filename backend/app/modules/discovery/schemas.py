from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DiscoverySearchRequest(BaseModel):
    platform: Literal["xiaohongshu"]
    query: str = Field(min_length=1, max_length=100)
    max_pages: int = Field(default=1, ge=1, le=5)
    hydrate_top: int = Field(default=0, ge=0, le=20)
    sort_type: Literal[
        "general",
        "time_descending",
        "popularity_descending",
        "comment_descending",
        "collect_descending",
        "english_preferred",
    ] = "general"
    note_type: Literal["不限", "视频笔记", "普通笔记", "直播笔记"] = "不限"
    time_filter: Literal["不限", "一天内", "一周内", "半年内"] = "不限"


class DiscoverySearchAccepted(BaseModel):
    search_id: UUID
    job_id: UUID
    status: str
    estimated_provider_cost_usd: Decimal


class DiscoverySearchEstimateRead(BaseModel):
    provider_calls: int
    estimated_provider_cost_usd: Decimal


class DiscoveryResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    external_id: str
    result_rank: int
    summary: dict
    imported_external_content_id: UUID | None


class DiscoverySearchRead(BaseModel):
    id: UUID
    sync_job_id: UUID | None
    platform: str
    query: str
    max_pages: int
    hydrate_top: int
    parameters: dict
    status: str
    result_count: int
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None
    results: list[DiscoveryResultRead]


class DiscoveryImportRequest(BaseModel):
    result_ids: list[UUID] = Field(min_length=1, max_length=100)
    hydrate: bool = False


class DiscoveryImportRead(BaseModel):
    inspiration_ids: list[UUID]
    hydration_job_ids: list[UUID]


class TrendingItemRead(BaseModel):
    inspiration_id: UUID
    external_content_id: UUID
    platform: str
    external_id: str
    canonical_url: str
    title: str | None
    published_at: datetime | None
    trend_score: int
    source: Literal["workspace_metric_snapshot"]
    evidence_snapshot_id: UUID
    evidence_captured_at: datetime
    metrics: dict[str, int | None]


class TrendingRefreshRead(BaseModel):
    queued_job_ids: list[UUID]
    skipped_inactive_count: int
