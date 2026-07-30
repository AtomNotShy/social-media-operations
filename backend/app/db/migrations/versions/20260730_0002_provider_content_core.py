"""Add provider evidence and normalized content tables.

Revision ID: 20260730_0002
Revises: 20260730_0001
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0002"
down_revision: str | None = "20260730_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "provider_fetches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("sync_job_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column("endpoint_key", sa.String(length=128), nullable=False),
        sa.Column("endpoint_path", sa.String(length=512), nullable=False),
        sa.Column("endpoint_version", sa.String(length=32), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("request_params_redacted", json_type, nullable=False),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("response_payload", json_type, nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("fresh_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_fetches_endpoint",
        "provider_fetches",
        ["endpoint_key", "fetched_at"],
    )
    op.create_index(
        "ix_provider_fetches_fingerprint",
        "provider_fetches",
        ["request_fingerprint", "fetched_at"],
    )
    op.create_index("ix_provider_fetches_sync_job_id", "provider_fetches", ["sync_job_id"])
    op.create_index("ix_provider_fetches_workspace_id", "provider_fetches", ["workspace_id"])

    op.create_table(
        "profile_metric_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("tracked_profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("followers", sa.BigInteger(), nullable=True),
        sa.Column("following", sa.BigInteger(), nullable=True),
        sa.Column("total_likes", sa.BigInteger(), nullable=True),
        sa.Column("content_count", sa.BigInteger(), nullable=True),
        sa.Column("metrics", json_type, nullable=False),
        sa.Column("provider_fetch_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["provider_fetch_id"], ["provider_fetches.id"]),
        sa.ForeignKeyConstraint(
            ["tracked_profile_id"],
            ["tracked_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracked_profile_id", "provider_fetch_id"),
    )
    op.create_index(
        "ix_profile_metric_snapshots_profile_captured",
        "profile_metric_snapshots",
        ["tracked_profile_id", "captured_at"],
    )
    op.create_index(
        "ix_profile_metric_snapshots_workspace_id",
        "profile_metric_snapshots",
        ["workspace_id"],
    )

    op.create_table(
        "external_contents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("tracked_profile_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("author_snapshot", json_type, nullable=False),
        sa.Column("media_manifest", json_type, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("detail_status", sa.String(length=16), nullable=False),
        sa.Column("comments_hydrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_provider_fetch_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["latest_provider_fetch_id"],
            ["provider_fetches.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tracked_profile_id"],
            ["tracked_profiles.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "platform", "external_id"),
    )
    op.create_index(
        "ix_external_contents_canonical_url",
        "external_contents",
        ["canonical_url"],
    )
    op.create_index(
        "ix_external_contents_profile_published",
        "external_contents",
        ["tracked_profile_id", "published_at"],
    )
    op.create_index(
        "ix_external_contents_workspace_published",
        "external_contents",
        ["workspace_id", "published_at"],
    )

    op.create_table(
        "workspace_inspirations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("manual_score", sa.SmallInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["external_content_id"],
            ["external_contents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "external_content_id"),
    )
    op.create_index(
        "ix_workspace_inspirations_workspace_id",
        "workspace_inspirations",
        ["workspace_id"],
    )

    op.create_table(
        "content_metric_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Uuid(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("views", sa.BigInteger(), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.Column("comments", sa.BigInteger(), nullable=True),
        sa.Column("favorites", sa.BigInteger(), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("downloads", sa.BigInteger(), nullable=True),
        sa.Column("metrics", json_type, nullable=False),
        sa.Column("provider_fetch_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["external_content_id"],
            ["external_contents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["provider_fetch_id"], ["provider_fetches.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_content_id", "provider_fetch_id"),
    )
    op.create_index(
        "ix_content_metric_snapshots_content_captured",
        "content_metric_snapshots",
        ["external_content_id", "captured_at"],
    )
    op.create_index(
        "ix_content_metric_snapshots_workspace_id",
        "content_metric_snapshots",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_table("content_metric_snapshots")
    op.drop_table("workspace_inspirations")
    op.drop_table("external_contents")
    op.drop_table("profile_metric_snapshots")
    op.drop_table("provider_fetches")
