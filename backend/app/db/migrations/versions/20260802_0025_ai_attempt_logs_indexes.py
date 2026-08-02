"""Add missing single-column indexes on ai_attempt_logs.

The model declares indexed FK columns (workspace_id, sync_job_id); the original
0023 migration only created the composite run index.  This closes the drift.

Revision ID: 20260802_0025
Revises: 20260802_0024
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260802_0025"
down_revision: str | None = "20260802_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_ai_attempt_logs_workspace_id",
        "ai_attempt_logs",
        ["workspace_id"],
    )
    op.create_index(
        "ix_ai_attempt_logs_sync_job_id",
        "ai_attempt_logs",
        ["sync_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_attempt_logs_sync_job_id", table_name="ai_attempt_logs")
    op.drop_index("ix_ai_attempt_logs_workspace_id", table_name="ai_attempt_logs")
