"""Add saved views, experiments and attribution evidence.

Revision ID: 20260730_0013
Revises: 20260730_0012
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0013"
down_revision: str | None = "20260730_0012"
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
        "saved_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query_params", json_type, nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", "entity_type", "name"),
    )
    op.create_index(
        "ix_saved_views_workspace_entity",
        "saved_views",
        ["workspace_id", "entity_type"],
    )
    op.create_index("ix_saved_views_workspace_id", "saved_views", ["workspace_id"])
    op.create_index("ix_saved_views_user_id", "saved_views", ["user_id"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owned_channel_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("primary_metric", sa.String(length=64), nullable=False),
        sa.Column("variants", json_type, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["owned_channel_id"],
            ["owned_channels.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_experiments_workspace_status",
        "experiments",
        ["workspace_id", "status"],
    )
    op.create_index("ix_experiments_workspace_id", "experiments", ["workspace_id"])

    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("content_project_id", sa.Uuid(), nullable=False),
        sa.Column("variant_key", sa.String(length=64), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["content_project_id"],
            ["content_projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "content_project_id"),
    )
    op.create_index(
        "ix_experiment_assignments_workspace_experiment",
        "experiment_assignments",
        ["workspace_id", "experiment_id"],
    )
    op.create_index(
        "ix_experiment_assignments_workspace_id",
        "experiment_assignments",
        ["workspace_id"],
    )

    op.create_table(
        "attribution_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("publish_record_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=2048), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["experiment_assignments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["publish_record_id"],
            ["publish_records.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
    )
    op.create_index(
        "ix_attribution_events_experiment_occurred",
        "attribution_events",
        ["experiment_id", "occurred_at"],
    )
    op.create_index(
        "ix_attribution_events_workspace_id",
        "attribution_events",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_table("attribution_events")
    op.drop_table("experiment_assignments")
    op.drop_table("experiments")
    op.drop_table("saved_views")
