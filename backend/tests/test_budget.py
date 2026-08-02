from decimal import Decimal

from app.modules.analysis.budget import estimate_generation_cost_usd


def test_estimate_generation_cost_scales_with_payload():
    cost = estimate_generation_cost_usd(
        provider="deepseek",
        model="deepseek-v4-flash",
        input_cost_per_million_usd=Decimal("1"),
        output_cost_per_million_usd=Decimal("2"),
        payload={"body": "中文" * 1000},
        expected_output_tokens=800,
    )
    # 2012 JSON chars -> 2012 input tokens at $1/M, 800 output tokens at $2/M.
    assert cost == Decimal("0.003612")


def test_estimate_generation_cost_zero_when_unpriced():
    assert (
        estimate_generation_cost_usd(
            provider="fixture",
            model="fixture-generation",
            input_cost_per_million_usd=Decimal("0"),
            output_cost_per_million_usd=Decimal("0"),
            payload={"body": "任何内容"},
        )
        == Decimal("0")
    )
