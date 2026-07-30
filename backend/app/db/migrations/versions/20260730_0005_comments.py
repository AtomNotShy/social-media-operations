"""Add limited comment sample storage.

Revision ID: 20260730_0005
Revises: 20260730_0004
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0005"
down_revision: str | None = "20260730_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "comment_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Uuid(), nullable=False),
        sa.Column("external_comment_id", sa.String(length=255), nullable=False),
        sa.Column("parent_external_id", sa.String(length=255), nullable=True),
        sa.Column("author_snapshot", json_type, nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("provider_fetch_id", sa.Uuid(), nullable=False),
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
            ["external_content_id"],
            ["external_contents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["provider_fetch_id"], ["provider_fetches.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "external_content_id", "external_comment_id"),
    )
    op.create_index(
        "ix_comment_samples_content_captured",
        "comment_samples",
        ["external_content_id", "captured_at"],
    )
    op.create_index("ix_comment_samples_workspace_id", "comment_samples", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("comment_samples")
