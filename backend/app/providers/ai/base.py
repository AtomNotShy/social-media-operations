from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.db.models import AnalysisRun, ExternalContent, Transcript


@dataclass(frozen=True, slots=True)
class AnalysisProviderResult:
    result: dict
    evidence_refs: list[str]
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None


class AnalysisProvider(Protocol):
    async def analyze(
        self,
        *,
        run: AnalysisRun,
        content: ExternalContent,
        transcript: Transcript | None,
    ) -> AnalysisProviderResult: ...
