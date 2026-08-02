"""Add self-owned channel scan fields for basic profile verification.

Revision ID: 20260802_0022
Revises: 20260802_0021
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0022"
down_revision: str | None = "20260802_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("owned_channels", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("owned_channels", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.add_column(
        "owned_channels",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "owned_channels",
        sa.Column(
            "sync_status",
            sa.String(length=16),
            server_default="idle",
            nullable=False,
        ),
    )
    op.add_column(
        "owned_channels",
        sa.Column("sync_error", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("owned_channels", "sync_error")
    op.drop_column("owned_channels", "sync_status")
    op.drop_column("owned_channels", "last_synced_at")
    op.drop_column("owned_channels", "avatar_url")
    op.drop_column("owned_channels", "bio")
