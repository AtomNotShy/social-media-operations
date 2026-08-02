"""Backfill official DeepSeek model pricing onto existing AI model routes.

Revision ID: 20260802_0024
Revises: 20260802_0023
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0024"
down_revision: str | None = "20260802_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OFFICIAL_PRICES = {
    "deepseek-v4-flash": ("0.140000", "0.280000"),
    "deepseek-v4-pro": ("0.435000", "0.870000"),
}


def upgrade() -> None:
    for model, (input_price, output_price) in _OFFICIAL_PRICES.items():
        connection = op.get_bind()
        connection.execute(
            sa.text(
                """
                UPDATE ai_model_routes AS r
                SET input_cost_per_million_usd = :input_price,
                    output_cost_per_million_usd = :output_price
                FROM ai_connections AS c
                WHERE c.id = r.connection_id
                  AND c.provider = 'deepseek'
                  AND r.model = :model
                """
            ).bindparams(
                sa.bindparam("input_price", type_=sa.Numeric(12, 6)),
                sa.bindparam("output_price", type_=sa.Numeric(12, 6)),
                sa.bindparam("model", type_=sa.String(128)),
            ),
            {
                "input_price": input_price,
                "output_price": output_price,
                "model": model,
            },
        )


def downgrade() -> None:
    # Price backfill is idempotent catalog data, not schema; nothing to undo.
    pass
