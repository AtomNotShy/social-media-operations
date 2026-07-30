from decimal import Decimal

from app.providers.asr.base import TranscriptProviderResult


class FixtureTranscriptProvider:
    async def transcribe(self, *, transcript, content, media_url):
        text = content.body_text or content.title or "Fixture transcript"
        return TranscriptProviderResult(
            text=text,
            segments=[{"start_ms": 0, "end_ms": 1000, "text": text}],
            language=content.language or "zh",
            confidence=Decimal("0.99"),
        )
