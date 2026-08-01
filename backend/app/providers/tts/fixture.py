from app.providers.tts.base import TTSOutput


class FixtureTTSProvider:
    """A test-only provider; the bytes are deliberately not a playable asset."""

    async def synthesize(self, *, text: str, voice_id: str | None) -> TTSOutput:
        return TTSOutput(
            audio=b"ID3\x04\x00\x00\x00\x00\x00\x00fixture-video-tts",
            mime_type="audio/mpeg",
            extension="mp3",
            estimated_duration_seconds=max(1.0, len(text) / 5.0),
        )
