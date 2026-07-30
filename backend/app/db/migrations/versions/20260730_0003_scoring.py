"""Add versioned scoring policies and immutable score evidence.

Revision ID: 20260730_0003
Revises: 20260730_0002
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0003"
down_revision: str | None = "20260730_0002"
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
        "scoring_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("core_metric_formula", json_type, nullable=False),
        sa.Column("tier_thresholds", json_type, nullable=False),
        sa.Column("grade_thresholds", json_type, nullable=False),
        sa.Column("minimum_age_minutes", sa.Integer(), nullable=False),
        sa.Column("minimum_baseline_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "platform", "version"),
    )
    op.create_index(
        "ix_scoring_policies_workspace_id",
        "scoring_policies",
        ["workspace_id"],
    )
    op.create_index(
        "uq_scoring_policies_active",
        "scoring_policies",
        ["workspace_id", "platform"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        sqlite_where=sa.text("active = 1"),
    )

    op.create_table(
        "content_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Uuid(), nullable=False),
        sa.Column("scoring_policy_id", sa.Uuid(), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("r_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("m_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("tier", sa.String(length=32), nullable=True),
        sa.Column("grade", sa.String(length=32), nullable=False),
        sa.Column("core_metric", sa.Numeric(18, 6), nullable=True),
        sa.Column("baseline_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("is_initial", sa.Boolean(), nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["external_content_id"],
            ["external_contents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["scoring_policy_id"], ["scoring_policies.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_scores_content_calculated",
        "content_scores",
        ["external_content_id", "calculated_at"],
    )
    op.create_index(
        "ix_content_scores_workspace_id",
        "content_scores",
        ["workspace_id"],
    )
    op.create_index(
        "uq_content_scores_initial",
        "content_scores",
        ["workspace_id", "external_content_id"],
        unique=True,
        postgresql_where=sa.text("is_initial = true"),
        sqlite_where=sa.text("is_initial = 1"),
    )


def downgrade() -> None:
    op.drop_table("content_scores")
    op.drop_table("scoring_policies")
