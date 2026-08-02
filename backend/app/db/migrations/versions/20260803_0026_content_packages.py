"""Create content_packages table.

Revision ID: 20260803_0026
Revises: 20260802_0025
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

json_type = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")

revision: str = "20260803_0026"
down_revision: str | None = "20260802_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("content_project_id", sa.Uuid(), nullable=False),
        sa.Column("script_version_id", sa.Uuid(), nullable=True),
        sa.Column("generation_run_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("target_platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("package", json_type, nullable=False),
        sa.Column("evidence_refs", json_type, nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            ["generation_run_id"],
            ["generation_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["script_version_id"],
            ["script_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "content_project_id",
            "target_platform",
            "version",
        ),
    )
    op.create_index(
        "ix_content_packages_workspace_id",
        "content_packages",
        ["workspace_id"],
    )
    op.create_index(
        "ix_content_packages_generation_run_id",
        "content_packages",
        ["generation_run_id"],
    )
    op.create_index(
        "ix_content_packages_project_platform",
        "content_packages",
        ["content_project_id", "target_platform", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_packages_project_platform", table_name="content_packages")
    op.drop_index("ix_content_packages_generation_run_id", table_name="content_packages")
    op.drop_index("ix_content_packages_workspace_id", table_name="content_packages")
    op.drop_table("content_packages")
