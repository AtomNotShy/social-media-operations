from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.workflow.schemas import ContentProjectRead, PublishPlanRead


class TodayDashboardRead(BaseModel):
    timezone: str
    window_start: datetime
    window_end: datetime
    projects_due: list[ContentProjectRead]
    publish_plans: list[PublishPlanRead]
    active_job_count: int
    published_waiting_review_count: int


class PerformanceTotals(BaseModel):
    published_count: int
    review_count: int
    exposure: int
    interactions: int
    conversions: int


class PerformanceRecordRead(BaseModel):
    publish_record_id: UUID
    publish_plan_id: UUID
    owned_channel_id: UUID
    platform: str
    content_title: str
    published_at: datetime
    published_url: str
    latest_review_window: str | None
    metrics: dict
    exposure: int
    interactions: int
    conversions: int


class PerformanceDashboardRead(BaseModel):
    from_at: datetime
    to_at: datetime
    totals: PerformanceTotals
    records: list[PerformanceRecordRead]
