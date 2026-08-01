"""Index expired collected-content retention candidates.

Revision ID: 20260801_0019
Revises: 20260801_0018
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0019"
down_revision: str | None = "20260801_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_external_contents_last_seen",
        "external_contents",
        ["last_seen_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_contents_last_seen", table_name="external_contents")
