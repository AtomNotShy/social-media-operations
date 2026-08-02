"""Versioned catalog of official AI model pricing.

DeepSeek and OpenAI connections must not rely on prices typed in by the
operator: cost estimates, daily-budget reservations and the ledger all derive
from this catalog at route-write and route-read time.  Custom OpenAI-compatible
endpoints keep the operator-supplied prices because they are not in any
official catalog.

The catalog is versioned by the source snapshot date.  Prices drift upstream,
so a future sync task can replace the snapshot without rewriting history rows
(runs already persist their own token counts and settled costs).
"""

from dataclasses import dataclass
from decimal import Decimal

# Snapshot date of the DeepSeek official pricing page this catalog mirrors.
# Source: https://api-docs.deepseek.com/quick_start/pricing/ (2026-07-23).
PRICING_CATALOG_VERSION = "deepseek-2026-07-23"
PRICING_SOURCE_URL = "https://api-docs.deepseek.com/quick_start/pricing/"


@dataclass(frozen=True, slots=True)
class ModelPricing:
    provider: str
    model: str
    input_cost_per_million_usd: Decimal
    output_cost_per_million_usd: Decimal
    cache_hit_input_cost_per_million_usd: Decimal | None = None
    currency: str = "USD"
    recommended_max_tokens: int | None = None
    notes: str | None = None


_OFFICIAL_MODEL_PRICING: dict[tuple[str, str], ModelPricing] = {
    ("deepseek", "deepseek-v4-flash"): ModelPricing(
        provider="deepseek",
        model="deepseek-v4-flash",
        input_cost_per_million_usd=Decimal("0.14"),
        output_cost_per_million_usd=Decimal("0.28"),
        cache_hit_input_cost_per_million_usd=Decimal("0.0028"),
        recommended_max_tokens=8192,
        notes=(
            "DeepSeek 官方 2026-07-23 定价快照；推理 token 计入 max_tokens，"
            "长文生成建议上调 max_tokens。"
        ),
    ),
    ("deepseek", "deepseek-v4-pro"): ModelPricing(
        provider="deepseek",
        model="deepseek-v4-pro",
        input_cost_per_million_usd=Decimal("0.435"),
        output_cost_per_million_usd=Decimal("0.87"),
        cache_hit_input_cost_per_million_usd=Decimal("0.003625"),
        recommended_max_tokens=8192,
        notes=(
            "DeepSeek 官方 2026-07-23 定价快照；推理 token 计入 max_tokens，"
            "长文生成建议上调 max_tokens。"
        ),
    ),
}


def official_price_for(provider: str, model: str) -> ModelPricing | None:
    return _OFFICIAL_MODEL_PRICING.get((provider.strip().lower(), model.strip()))


def official_model_prices() -> list[ModelPricing]:
    return sorted(
        _OFFICIAL_MODEL_PRICING.values(),
        key=lambda item: (item.provider, item.model),
    )


def effective_route_prices(
    *,
    provider: str,
    model: str,
    stored_input_cost_per_million_usd: Decimal,
    stored_output_cost_per_million_usd: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return the prices a route should be valued at for estimation and ledger.

    Official catalog prices win for models we know; operator-supplied prices are
    only used for custom providers/models.  This keeps already-created routes
    with zero or stale prices correct without waiting for a backfill.
    """
    official = official_price_for(provider, model)
    if official is not None:
        return (
            official.input_cost_per_million_usd,
            official.output_cost_per_million_usd,
        )
    return stored_input_cost_per_million_usd, stored_output_cost_per_million_usd
