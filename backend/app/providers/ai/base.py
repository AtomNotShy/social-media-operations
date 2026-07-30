from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.db.models import AnalysisRun, ExternalContent, Transcript


class AIProviderRequestError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


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
        metrics: dict | None = None,
    ) -> AnalysisProviderResult: ...
