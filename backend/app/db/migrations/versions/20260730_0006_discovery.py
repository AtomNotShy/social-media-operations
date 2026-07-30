"""Add isolated discovery search results.

Revision ID: 20260730_0006
Revises: 20260730_0005
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
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
        "discovery_searches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("sync_job_id", sa.Uuid(), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("max_pages", sa.SmallInteger(), nullable=False),
        sa.Column("hydrate_top", sa.SmallInteger(), nullable=False),
        sa.Column("parameters", json_type, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discovery_searches_workspace_created",
        "discovery_searches",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_discovery_searches_sync_job_id",
        "discovery_searches",
        ["sync_job_id"],
    )
    op.create_index(
        "ix_discovery_searches_workspace_id",
        "discovery_searches",
        ["workspace_id"],
    )

    op.create_table(
        "discovery_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("discovery_search_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("result_rank", sa.Integer(), nullable=False),
        sa.Column("summary", json_type, nullable=False),
        sa.Column("provider_fetch_id", sa.Uuid(), nullable=False),
        sa.Column("imported_external_content_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["discovery_search_id"],
            ["discovery_searches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["imported_external_content_id"],
            ["external_contents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["provider_fetch_id"], ["provider_fetches.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discovery_search_id", "platform", "external_id"),
    )
    op.create_index(
        "ix_discovery_results_search_rank",
        "discovery_results",
        ["discovery_search_id", "result_rank"],
    )
    op.create_index(
        "ix_discovery_results_workspace_id",
        "discovery_results",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_table("discovery_results")
    op.drop_table("discovery_searches")
