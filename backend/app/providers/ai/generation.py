from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.db.models import GenerationRun


@dataclass(frozen=True, slots=True)
class GenerationProviderResult:
    result: dict
    evidence_refs: list[str]
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None


class ContentGenerationProvider(Protocol):
    async def generate(self, *, run: GenerationRun) -> GenerationProviderResult: ...


class FixtureContentGenerationProvider:
    async def generate(self, *, run: GenerationRun) -> GenerationProviderResult:
        if run.generation_type == "script_draft":
            return GenerationProviderResult(
                result={
                    "body": "开场：餐厅高峰期最怕的不是忙，而是漏单。\n"
                    "主体：用清晰流程展示问题、证据和解决方案。\n"
                    "结尾：保存这份检查清单并在下次高峰前演练。",
                    "structured_body": {
                        "sections": ["hook", "evidence", "solution", "call_to_action"]
                    },
                    "rationale": "Fixture result for schema and workflow validation.",
                    "evidence_refs": run.evidence_refs,
                },
                evidence_refs=run.evidence_refs,
            )
        return GenerationProviderResult(
            result={
                "analysis": {
                    "summary": "The fixture metrics show measurable exposure and engagement.",
                    "primary_metric": run.input_payload.get("primary_metric"),
                },
                "next_actions": ["Keep the winning hook and test one variable next."],
                "evidence_refs": run.evidence_refs,
            },
            evidence_refs=run.evidence_refs,
        )
