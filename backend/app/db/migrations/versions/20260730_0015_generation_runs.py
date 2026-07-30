"""Add auditable AI content generation runs.

Revision ID: 20260730_0015
Revises: 20260730_0014
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0015"
down_revision: str | None = "20260730_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("content_project_id", sa.Uuid(), nullable=False),
        sa.Column("publish_record_id", sa.Uuid(), nullable=True),
        sa.Column("sync_job_id", sa.Uuid(), nullable=True),
        sa.Column("generation_type", sa.String(length=32), nullable=False),
        sa.Column("model_provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input_payload", json_type, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["content_project_id"],
            ["content_projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["publish_record_id"],
            ["publish_records.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generation_runs_project_created",
        "generation_runs",
        ["content_project_id", "created_at"],
    )
    op.create_index(
        "ix_generation_runs_sync_job_id",
        "generation_runs",
        ["sync_job_id"],
    )
    op.create_index(
        "ix_generation_runs_workspace_id",
        "generation_runs",
        ["workspace_id"],
    )
    op.create_index(
        "uq_generation_runs_reusable",
        "generation_runs",
        ["workspace_id", "generation_type", "input_hash"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'succeeded')"),
        sqlite_where=sa.text("status IN ('queued', 'running', 'succeeded')"),
    )


def downgrade() -> None:
    op.drop_table("generation_runs")
