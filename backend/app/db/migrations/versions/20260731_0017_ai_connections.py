"""Add encrypted workspace AI connections and model routes.

Revision ID: 20260731_0017
Revises: 20260731_0016
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260731_0017"
down_revision: str | None = "20260731_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ai_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("api_key_last_four", sa.String(length=4), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("capabilities", json_type, nullable=False),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name"),
    )
    op.create_index("ix_ai_connections_workspace_id", "ai_connections", ["workspace_id"])

    op.create_table(
        "ai_model_routes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("temperature", sa.Numeric(4, 3), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("input_cost_per_million_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("output_cost_per_million_usd", sa.Numeric(12, 6), nullable=False),
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
            ["connection_id"],
            ["ai_connections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "task_type"),
    )
    op.create_index("ix_ai_model_routes_connection_id", "ai_model_routes", ["connection_id"])
    op.create_index("ix_ai_model_routes_workspace_id", "ai_model_routes", ["workspace_id"])

    with op.batch_alter_table("analysis_runs") as batch:
        batch.add_column(sa.Column("ai_connection_id", sa.Uuid(), nullable=True))
        batch.create_index(
            "ix_analysis_runs_ai_connection_id",
            ["ai_connection_id"],
            unique=False,
        )
        batch.create_foreign_key(
            "fk_analysis_runs_ai_connection_id",
            "ai_connections",
            ["ai_connection_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("generation_runs") as batch:
        batch.add_column(sa.Column("ai_connection_id", sa.Uuid(), nullable=True))
        batch.create_index(
            "ix_generation_runs_ai_connection_id",
            ["ai_connection_id"],
            unique=False,
        )
        batch.create_foreign_key(
            "fk_generation_runs_ai_connection_id",
            "ai_connections",
            ["ai_connection_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("generation_runs") as batch:
        batch.drop_constraint("fk_generation_runs_ai_connection_id", type_="foreignkey")
        batch.drop_index("ix_generation_runs_ai_connection_id")
        batch.drop_column("ai_connection_id")
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_constraint("fk_analysis_runs_ai_connection_id", type_="foreignkey")
        batch.drop_index("ix_analysis_runs_ai_connection_id")
        batch.drop_column("ai_connection_id")
    op.drop_table("ai_model_routes")
    op.drop_table("ai_connections")
