"""Change the default profile scan cadence to daily.

Revision ID: 20260731_0016
Revises: 20260730_0015
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260731_0016"
down_revision: str | None = "20260730_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

scan_policies = sa.table(
    "scan_policies",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.String()),
    sa.column("schedule", json_type),
)


def _replace_default_interval(from_hours: int, to_hours: int) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(scan_policies.c.id, scan_policies.c.schedule).where(
            scan_policies.c.name == "默认扫描策略"
        )
    )
    for policy_id, schedule in rows:
        if not isinstance(schedule, dict) or schedule.get("interval_hours") != from_hours:
            continue
        updated_schedule = {**schedule, "interval_hours": to_hours}
        connection.execute(
            sa.update(scan_policies)
            .where(scan_policies.c.id == policy_id)
            .values(schedule=updated_schedule)
        )


def upgrade() -> None:
    _replace_default_interval(6, 24)


def downgrade() -> None:
    _replace_default_interval(24, 6)
