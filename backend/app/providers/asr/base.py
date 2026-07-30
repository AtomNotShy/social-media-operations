from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.db.models import ExternalContent, Transcript


@dataclass(frozen=True, slots=True)
class TranscriptProviderResult:
    text: str
    segments: list[dict]
    language: str | None = None
    confidence: Decimal | None = None
    cost_usd: Decimal = Decimal("0")


class TranscriptProvider(Protocol):
    async def transcribe(
        self,
        *,
        transcript: Transcript,
        content: ExternalContent,
        media_url: str,
    ) -> TranscriptProviderResult: ...
