from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TTSOutput:
    audio: bytes
    mime_type: str
    extension: str
    estimated_duration_seconds: float


class TTSProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class TTSProvider(Protocol):
    async def synthesize(self, *, text: str, voice_id: str | None) -> TTSOutput: ...
