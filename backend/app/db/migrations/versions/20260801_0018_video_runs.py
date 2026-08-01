"""Add durable local video production runs.

Revision ID: 20260801_0018
Revises: 20260731_0017
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260801_0018"
down_revision: str | None = "20260731_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "video_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("content_project_id", sa.Uuid(), nullable=False),
        sa.Column("script_version_id", sa.Uuid(), nullable=False),
        sa.Column("sync_job_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tts_provider", sa.String(length=32), nullable=False),
        sa.Column("voice_id", sa.String(length=255), nullable=True),
        sa.Column("render_spec", json_type, nullable=False),
        sa.Column("request_payload", json_type, nullable=False),
        sa.Column("result", json_type, nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_project_id"], ["content_projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["script_version_id"], ["script_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_video_runs_workspace_id", "video_runs", ["workspace_id"])
    op.create_index("ix_video_runs_sync_job_id", "video_runs", ["sync_job_id"])
    op.create_index(
        "ix_video_runs_project_created", "video_runs", ["content_project_id", "created_at"]
    )
    op.create_index("ix_video_runs_workspace_status", "video_runs", ["workspace_id", "status"])
    op.create_index(
        "uq_video_runs_active_dedupe",
        "video_runs",
        ["workspace_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_video_runs_active_dedupe", table_name="video_runs")
    op.drop_index("ix_video_runs_workspace_status", table_name="video_runs")
    op.drop_index("ix_video_runs_project_created", table_name="video_runs")
    op.drop_index("ix_video_runs_sync_job_id", table_name="video_runs")
    op.drop_index("ix_video_runs_workspace_id", table_name="video_runs")
    op.drop_table("video_runs")
