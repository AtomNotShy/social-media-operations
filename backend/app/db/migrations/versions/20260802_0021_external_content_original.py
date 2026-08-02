"""Store structured original content for faithful source display.

Revision ID: 20260802_0021
Revises: 20260801_0020
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0021"
down_revision: str | None = "20260801_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "external_contents",
        sa.Column("original_content", json_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_contents", "original_content")
