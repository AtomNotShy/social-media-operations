"""Add AI and transcription budget reservations.

Revision ID: 20260730_0012
Revises: 20260730_0011
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0012"
down_revision: str | None = "20260730_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_cost_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("sync_job_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=16), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("actual_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sync_job_id"),
    )
    op.create_index(
        "ix_ai_cost_ledger_resource_id",
        "ai_cost_ledger",
        ["resource_id"],
    )
    op.create_index(
        "ix_ai_cost_ledger_sync_job_id",
        "ai_cost_ledger",
        ["sync_job_id"],
    )
    op.create_index(
        "ix_ai_cost_ledger_workspace_date",
        "ai_cost_ledger",
        ["workspace_id", "usage_date"],
    )
    op.create_index(
        "ix_ai_cost_ledger_workspace_id",
        "ai_cost_ledger",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_table("ai_cost_ledger")
