"""Backfill active X scoring policies for historical workspaces.

Revision ID: 20260801_0020
Revises: 20260801_0019
Create Date: 2026-08-01
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260801_0020"
down_revision: str | None = "20260801_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

DEFAULT_X_SCORING_POLICY = {
    "core_metric_formula": {
        "required_metrics": ["likes", "comments", "favorites"],
        "core_metric_weights": {
            "likes": 1,
            "comments": 2,
            "favorites": 2,
            "shares": 3,
        },
        "reach_proxy_weights": {
            "likes": 1,
            "comments": 2,
            "favorites": 2,
            "shares": 3,
        },
    },
    "tier_thresholds": {
        "micro_max": 10000,
        "small_max": 100000,
        "medium_max": 1000000,
    },
    "grade_thresholds": {
        "t1": {"minimum_r": 5, "minimum_m": 0.1},
        "t2": {"minimum_r": 3, "minimum_m": 0.05},
        "t3": {"minimum_r": 2, "minimum_m": 0},
        "low_quality": {"maximum_r": 0.5},
    },
    "minimum_age_minutes": 60,
    "minimum_baseline_count": 5,
}

workspaces = sa.table("workspaces", sa.column("id", sa.Uuid()))
scoring_policies = sa.table(
    "scoring_policies",
    sa.column("id", sa.Uuid()),
    sa.column("workspace_id", sa.Uuid()),
    sa.column("platform", sa.String()),
    sa.column("version", sa.Integer()),
    sa.column("core_metric_formula", json_type),
    sa.column("tier_thresholds", json_type),
    sa.column("grade_thresholds", json_type),
    sa.column("minimum_age_minutes", sa.Integer()),
    sa.column("minimum_baseline_count", sa.Integer()),
    sa.column("active", sa.Boolean()),
)


def upgrade() -> None:
    connection = op.get_bind()
    x_policies = scoring_policies.alias("x_policies")
    active_x_policies = scoring_policies.alias("active_x_policies")
    has_active_x_policy = sa.exists(
        sa.select(sa.literal(1)).where(
            active_x_policies.c.workspace_id == workspaces.c.id,
            active_x_policies.c.platform == "x",
            active_x_policies.c.active.is_(True),
        )
    )
    missing_policy_workspaces = connection.execute(
        sa.select(
            workspaces.c.id,
            sa.func.coalesce(sa.func.max(x_policies.c.version), 0).label(
                "max_version"
            ),
        )
        .select_from(
            workspaces.outerjoin(
                x_policies,
                sa.and_(
                    x_policies.c.workspace_id == workspaces.c.id,
                    x_policies.c.platform == "x",
                ),
            )
        )
        .where(~has_active_x_policy)
        .group_by(workspaces.c.id)
    ).all()
    policies = [
        {
            "id": uuid4(),
            "workspace_id": workspace_id,
            "platform": "x",
            "version": int(max_version) + 1,
            **DEFAULT_X_SCORING_POLICY,
            "active": True,
        }
        for workspace_id, max_version in missing_policy_workspaces
    ]
    if policies:
        connection.execute(sa.insert(scoring_policies), policies)


def downgrade() -> None:
    # Do not remove backfilled policies: they may have since been edited or referenced.
    pass
