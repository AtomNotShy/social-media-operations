import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
ACTIVE_JOB_STATUSES = ("pending", "running", "retry_wait")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    external_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    daily_provider_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("5.0000"), nullable=False
    )
    daily_ai_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("5.0000"), nullable=False
    )
    settings: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    workspace: Mapped[Workspace] = relationship()
    user: Mapped[User] = relationship()


class AIConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_connections"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    api_key_last_four: Mapped[str | None] = mapped_column(String(4))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)


class AIModelRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_model_routes"
    __table_args__ = (UniqueConstraint("workspace_id", "task_type"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    temperature: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("0.2"), nullable=False
    )
    max_tokens: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    input_cost_per_million_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    output_cost_per_million_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )

    connection: Mapped[AIConnection] = relationship()


class ScanPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scan_policies"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    detail_policy: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    metric_refresh_policy: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    comment_policy: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TrackedProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tracked_profiles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "platform", "external_id"),
        Index("ix_tracked_profiles_workspace_created", "workspace_id", "created_at", "id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    follower_count_latest: Mapped[int | None] = mapped_column(BigInteger)
    priority: Mapped[int] = mapped_column(SmallInteger, default=50, nullable=False)
    scan_policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scan_policies.id"), nullable=False
    )
    sync_cursor: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str] = mapped_column(String(16), default="idle", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scan_policy: Mapped[ScanPolicy] = relationship()


class ProviderFetch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_fetches"
    __table_args__ = (
        Index("ix_provider_fetches_fingerprint", "request_fingerprint", "fetched_at"),
        Index("ix_provider_fetches_endpoint", "endpoint_key", "fetched_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(32))
    endpoint_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_path: Mapped[str] = mapped_column(String(512), nullable=False)
    endpoint_version: Mapped[str | None] = mapped_column(String(32))
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    request_params_redacted: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    http_status: Mapped[int | None] = mapped_column(Integer)
    provider_code: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    billable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    response_payload: Mapped[dict | None] = mapped_column(JSON_TYPE)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    fresh_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))


class ProfileMetricSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profile_metric_snapshots"
    __table_args__ = (
        UniqueConstraint("tracked_profile_id", "provider_fetch_id"),
        Index(
            "ix_profile_metric_snapshots_profile_captured",
            "tracked_profile_id",
            "captured_at",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tracked_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracked_profiles.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    followers: Mapped[int | None] = mapped_column(BigInteger)
    following: Mapped[int | None] = mapped_column(BigInteger)
    total_likes: Mapped[int | None] = mapped_column(BigInteger)
    content_count: Mapped[int | None] = mapped_column(BigInteger)
    metrics: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    provider_fetch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_fetches.id"), nullable=False
    )


class ExternalContent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_contents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "platform", "external_id"),
        Index("ix_external_contents_workspace_published", "workspace_id", "published_at"),
        Index("ix_external_contents_profile_published", "tracked_profile_id", "published_at"),
        Index("ix_external_contents_last_seen", "last_seen_at", "id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tracked_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tracked_profiles.id", ondelete="SET NULL")
    )
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    language: Mapped[str | None] = mapped_column(String(32))
    author_snapshot: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    media_manifest: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    detail_status: Mapped[str] = mapped_column(String(16), default="summary", nullable=False)
    comments_hydrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_provider_fetch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provider_fetches.id", ondelete="SET NULL")
    )


class WorkspaceInspiration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_inspirations"
    __table_args__ = (UniqueConstraint("workspace_id", "external_content_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_contents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="inbox", nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    manual_score: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ContentMetricSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_metric_snapshots"
    __table_args__ = (
        UniqueConstraint("external_content_id", "provider_fetch_id"),
        Index(
            "ix_content_metric_snapshots_content_captured",
            "external_content_id",
            "captured_at",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_contents.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    views: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    favorites: Mapped[int | None] = mapped_column(BigInteger)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    downloads: Mapped[int | None] = mapped_column(BigInteger)
    metrics: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    provider_fetch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_fetches.id"), nullable=False
    )


class CommentSample(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "comment_samples"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_content_id", "external_comment_id"),
        Index("ix_comment_samples_content_captured", "external_content_id", "captured_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_contents.id", ondelete="CASCADE"), nullable=False
    )
    external_comment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_external_id: Mapped[str | None] = mapped_column(String(255))
    author_snapshot: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    provider_fetch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_fetches.id"), nullable=False
    )


class SyncJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (
        Index("ix_sync_jobs_claim", "status", "run_after", "priority"),
        Index(
            "uq_sync_jobs_active_dedupe",
            "workspace_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running', 'retry_wait')"),
            sqlite_where=text("status IN ('pending', 'running', 'retry_wait')"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(512), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, default=50, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(255))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON_TYPE)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderUsageDaily(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_usage_daily"
    __table_args__ = (UniqueConstraint("workspace_id", "usage_date", "provider", "endpoint_key"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    billable_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )


class ProviderCircuitState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_circuit_states"
    __table_args__ = (UniqueConstraint("workspace_id", "provider", "endpoint_key"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint_key: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(16), default="closed", nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))


class ScoringPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scoring_policies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "platform", "version"),
        Index(
            "uq_scoring_policies_active",
            "workspace_id",
            "platform",
            unique=True,
            postgresql_where=text("active = true"),
            sqlite_where=text("active = 1"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    core_metric_formula: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    tier_thresholds: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    grade_thresholds: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    minimum_age_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    minimum_baseline_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ContentScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_scores"
    __table_args__ = (
        Index(
            "ix_content_scores_content_calculated",
            "external_content_id",
            "calculated_at",
        ),
        Index(
            "uq_content_scores_initial",
            "workspace_id",
            "external_content_id",
            unique=True,
            postgresql_where=text("is_initial = true"),
            sqlite_where=text("is_initial = 1"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_contents.id", ondelete="CASCADE"), nullable=False
    )
    scoring_policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scoring_policies.id"), nullable=False
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    r_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    m_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    tier: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(32), nullable=False)
    core_metric: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    is_initial: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class Transcript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "external_content_id",
            "input_hash",
            "provider",
            "model",
        ),
        Index("ix_transcripts_content_created", "external_content_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_contents.id", ondelete="CASCADE"), nullable=False
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    segments: Mapped[list | None] = mapped_column(JSON_TYPE)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_content_created", "external_content_id", "created_at"),
        Index(
            "uq_analysis_runs_reusable",
            "workspace_id",
            "analysis_level",
            "input_hash",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'succeeded')"),
            sqlite_where=text("status IN ('queued', 'running', 'succeeded')"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_contents.id", ondelete="CASCADE"), nullable=False
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    ai_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_connections.id", ondelete="SET NULL"), index=True
    )
    analysis_level: Mapped[str] = mapped_column(String(8), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON_TYPE)
    evidence_refs: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GenerationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_runs"
    __table_args__ = (
        Index("ix_generation_runs_project_created", "content_project_id", "created_at"),
        Index(
            "uq_generation_runs_reusable",
            "workspace_id",
            "generation_type",
            "input_hash",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'succeeded')"),
            sqlite_where=text("status IN ('queued', 'running', 'succeeded')"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE"), nullable=False
    )
    publish_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publish_records.id", ondelete="SET NULL")
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    ai_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_connections.id", ondelete="SET NULL"), index=True
    )
    generation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON_TYPE)
    evidence_refs: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VideoRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A durable request for a locally rendered social video.

    The run owns the job metadata, while all render artifacts live beneath the
    configured local video-runs directory.  Keep the local path out of the API
    surface: it is an implementation detail and must never be client supplied.
    """

    __tablename__ = "video_runs"
    __table_args__ = (
        Index("ix_video_runs_project_created", "content_project_id", "created_at"),
        Index("ix_video_runs_workspace_status", "workspace_id", "status"),
        Index(
            "uq_video_runs_active_dedupe",
            "workspace_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE"), nullable=False
    )
    script_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("script_versions.id", ondelete="RESTRICT"), nullable=False
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    tts_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    voice_id: Mapped[str | None] = mapped_column(String(255))
    render_spec: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON_TYPE)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class AICostLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_cost_ledger"
    __table_args__ = (
        UniqueConstraint("sync_job_id"),
        Index("ix_ai_cost_ledger_workspace_date", "workspace_id", "usage_date"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sync_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="reserved", nullable=False)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiscoverySearch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discovery_searches"
    __table_args__ = (
        Index("ix_discovery_searches_workspace_created", "workspace_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    max_pages: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hydrate_top: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiscoveryResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discovery_results"
    __table_args__ = (
        UniqueConstraint("discovery_search_id", "platform", "external_id"),
        Index("ix_discovery_results_search_rank", "discovery_search_id", "result_rank"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discovery_search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery_searches.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    result_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    provider_fetch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_fetches.id"), nullable=False
    )
    imported_external_content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("external_contents.id", ondelete="SET NULL")
    )


class ReusablePattern(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reusable_patterns"
    __table_args__ = (Index("ix_reusable_patterns_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(32), nullable=False)
    applicable_channels: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    source_content_ids: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class OwnedChannel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "owned_channels"
    __table_args__ = (
        Index(
            "uq_owned_channels_external",
            "workspace_id",
            "platform",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(255))
    positioning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    audience: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    content_pillars: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    tone_rules: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    prohibited_topics: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    publishing_mode: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (Index("ix_topics_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owned_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("owned_channels.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    audience_problem: Mapped[str | None] = mapped_column(Text)
    angle: Mapped[str | None] = mapped_column(Text)
    hook: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="idea", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContentProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_projects"
    __table_args__ = (Index("ix_content_projects_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    owned_channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("owned_channels.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="idea", nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScriptVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "script_versions"
    __table_args__ = (
        UniqueConstraint("content_project_id", "version_no"),
        Index("ix_script_versions_project_version", "content_project_id", "version_no"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    structured_body: Mapped[dict | None] = mapped_column(JSON_TYPE)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    change_note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssetUploadIntent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_upload_intents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE")
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rights_note: Mapped[str | None] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_workspace_project", "workspace_id", "content_project_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE")
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rights_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublishPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publish_plans"
    __table_args__ = (
        Index("ix_publish_plans_workspace_scheduled", "workspace_id", "scheduled_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE"), nullable=False
    )
    owned_channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("owned_channels.id"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    publishing_mode: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    publish_payload: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PublishRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publish_records"
    __table_args__ = (UniqueConstraint("publish_plan_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    publish_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publish_plans.id", ondelete="CASCADE"), nullable=False
    )
    platform_content_id: Mapped[str | None] = mapped_column(String(255))
    published_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ReviewInsight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_insights"
    __table_args__ = (
        Index("ix_review_insights_record_created", "publish_record_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    publish_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publish_records.id", ondelete="CASCADE"), nullable=False
    )
    review_window: Mapped[str] = mapped_column(String(16), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    analysis: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    next_actions: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_workspace_created", "workspace_id", "created_at"),
        Index("ix_audit_events_actor_created", "actor_user_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(128))
    target_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SavedView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_views"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", "entity_type", "name"),
        Index("ix_saved_views_workspace_entity", "workspace_id", "entity_type"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query_params: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owned_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("owned_channels.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    variants: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ExperimentAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "content_project_id"),
        Index("ix_experiment_assignments_workspace_experiment", "workspace_id", "experiment_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    content_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE"), nullable=False
    )
    variant_key: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class AttributionEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attribution_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key"),
        Index("ix_attribution_events_experiment_occurred", "experiment_id", "occurred_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_assignments.id", ondelete="CASCADE"), nullable=False
    )
    publish_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publish_records.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(2048), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)


class ProcessHeartbeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "process_heartbeats"
    __table_args__ = (
        UniqueConstraint("instance_id"),
        Index("ix_process_heartbeats_service_heartbeat", "service", "heartbeat_at"),
    )

    instance_id: Mapped[str] = mapped_column(String(255), nullable=False)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="SET NULL")
    )
