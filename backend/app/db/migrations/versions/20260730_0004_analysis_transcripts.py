"""Add transcript and analysis run ledgers.

Revision ID: 20260730_0004
Revises: 20260730_0003
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0004"
down_revision: str | None = "20260730_0003"
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
        "transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Uuid(), nullable=False),
        sa.Column("sync_job_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("segments", json_type, nullable=True),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["external_content_id"],
            ["external_contents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "external_content_id",
            "input_hash",
            "provider",
            "model",
        ),
    )
    op.create_index(
        "ix_transcripts_content_created",
        "transcripts",
        ["external_content_id", "created_at"],
    )
    op.create_index("ix_transcripts_sync_job_id", "transcripts", ["sync_job_id"])
    op.create_index("ix_transcripts_workspace_id", "transcripts", ["workspace_id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Uuid(), nullable=False),
        sa.Column("sync_job_id", sa.Uuid(), nullable=True),
        sa.Column("analysis_level", sa.String(length=8), nullable=False),
        sa.Column("model_provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", json_type, nullable=True),
        sa.Column("evidence_refs", json_type, nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["external_content_id"],
            ["external_contents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_runs_content_created",
        "analysis_runs",
        ["external_content_id", "created_at"],
    )
    op.create_index("ix_analysis_runs_sync_job_id", "analysis_runs", ["sync_job_id"])
    op.create_index("ix_analysis_runs_workspace_id", "analysis_runs", ["workspace_id"])
    op.create_index(
        "uq_analysis_runs_reusable",
        "analysis_runs",
        ["workspace_id", "analysis_level", "input_hash"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'succeeded')"),
        sqlite_where=sa.text("status IN ('queued', 'running', 'succeeded')"),
    )


def downgrade() -> None:
    op.drop_table("analysis_runs")
    op.drop_table("transcripts")
