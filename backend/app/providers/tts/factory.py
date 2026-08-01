import httpx

from app.core.config import Settings
from app.providers.tts.base import TTSProvider, TTSProviderError
from app.providers.tts.fixture import FixtureTTSProvider
from app.providers.tts.providers import ElevenLabsTTSProvider, MiniMaxTTSProvider


def build_tts_provider(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> TTSProvider:
    if settings.video_tts_provider == "fixture":
        return FixtureTTSProvider()
    if settings.video_tts_provider == "minimax":
        assert settings.minimax_api_key is not None
        return MiniMaxTTSProvider(
            api_key=settings.minimax_api_key.get_secret_value(),
            model=settings.minimax_tts_model,
            timeout_seconds=settings.video_tts_timeout_seconds,
            client=client,
        )
    if settings.video_tts_provider == "elevenlabs":
        assert settings.elevenlabs_api_key is not None
        return ElevenLabsTTSProvider(
            api_key=settings.elevenlabs_api_key.get_secret_value(),
            base_url=settings.elevenlabs_base_url,
            model_id=settings.elevenlabs_model_id,
            timeout_seconds=settings.video_tts_timeout_seconds,
            client=client,
        )
    raise TTSProviderError(
        "VIDEO_TTS_NOT_CONFIGURED",
        "Set VIDEO_TTS_PROVIDER to minimax or elevenlabs before rendering videos.",
        retryable=False,
    )
