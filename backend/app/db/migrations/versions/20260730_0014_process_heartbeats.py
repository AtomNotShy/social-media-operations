"""Add worker and scheduler process heartbeats.

Revision ID: 20260730_0014
Revises: 20260730_0013
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0014"
down_revision: str | None = "20260730_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "process_heartbeats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instance_id", sa.String(length=255), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["current_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id"),
    )
    op.create_index(
        "ix_process_heartbeats_service_heartbeat",
        "process_heartbeats",
        ["service", "heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_table("process_heartbeats")
