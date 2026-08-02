from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal[
    "douyin",
    "xiaohongshu",
    "youtube",
    "bilibili",
    "kuaishou",
    "weibo",
    "wechat_channels",
    "tiktok",
    "instagram",
    "x",
]


class TrackedProfileCreate(BaseModel):
    platform: Platform
    external_id: str = Field(min_length=1, max_length=255)
    profile_url: str = Field(min_length=8, max_length=2048)
    display_name: str = Field(min_length=1, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    priority: int = Field(default=50, ge=0, le=100)
    scan_policy_id: UUID | None = None


class TrackedProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    priority: int | None = Field(default=None, ge=0, le=100)


class TrackedProfileImportRequest(BaseModel):
    profiles: list[TrackedProfileCreate] = Field(min_length=1, max_length=100)


class TrackedProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    platform: str
    external_id: str
    profile_url: str
    display_name: str
    avatar_url: str | None
    handle: str | None
    follower_count_latest: int | None
    priority: int
    scan_policy_id: UUID
    last_synced_at: datetime | None
    next_scan_at: datetime | None
    sync_status: str
    active: bool
    created_at: datetime
    updated_at: datetime


class ProfileMetricSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    captured_at: datetime
    followers: int | None
    following: int | None
    total_likes: int | None
    content_count: int | None
    metrics: dict
    provider_fetch_id: UUID


class ExternalContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    external_id: str
    tracked_profile_id: UUID | None
    canonical_url: str
    content_type: str
    title: str | None
    body_text: str | None
    published_at: datetime | None
    duration_ms: int | None
    author_snapshot: dict
    media_manifest: list
    original_content: dict | None = None
    detail_status: str
    first_seen_at: datetime
    last_seen_at: datetime


class TrackedProfileOverviewGradeDistribution(BaseModel):
    t1: int = 0
    t2: int = 0
    t3: int = 0
    qualified: int = 0
    normal: int = 0


class TrackedProfileOverviewMetricSummary(BaseModel):
    captured_at: datetime
    views: int | None
    likes: int | None
    comments: int | None
    favorites: int | None
    shares: int | None
    downloads: int | None


class TrackedProfileOverviewScoreSummary(BaseModel):
    calculated_at: datetime
    grade: str
    tier: str | None
    r_value: Decimal | None
    m_value: Decimal | None


class TrackedProfileOverviewContent(BaseModel):
    id: UUID
    platform: str
    external_id: str
    canonical_url: str
    content_type: str
    title: str | None
    cover_url: str | None
    published_at: datetime | None
    first_seen_at: datetime
    latest_metrics: TrackedProfileOverviewMetricSummary | None
    latest_score: TrackedProfileOverviewScoreSummary | None
    in_inspiration_library: bool
    inspiration_id: UUID | None


class TrackedProfileOverviewRead(BaseModel):
    profile: TrackedProfileRead
    window_days: int
    total_content_count: int
    recent_content_count: int
    grade_distribution: TrackedProfileOverviewGradeDistribution
    contents: list[TrackedProfileOverviewContent]
