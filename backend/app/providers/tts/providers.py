import httpx

from app.providers.tts.base import TTSOutput, TTSProviderError


def _duration(text: str) -> float:
    return max(1.0, len(text) / 5.0)


class _HTTPProvider:
    def __init__(self, *, timeout_seconds: int, client: httpx.AsyncClient | None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        try:
            if self.client is not None:
                response = await self.client.request(method, url, **kwargs)
            else:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise TTSProviderError(
                "TTS_TIMEOUT", "TTS provider timed out.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise TTSProviderError(
                "TTS_UNAVAILABLE", "TTS provider is unavailable.", retryable=True
            ) from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise TTSProviderError(
                "TTS_PROVIDER_UNAVAILABLE", "TTS provider rejected the request.", retryable=True
            )
        if response.status_code >= 400:
            raise TTSProviderError(
                "TTS_PROVIDER_REJECTED", "TTS provider rejected the request.", retryable=False
            )
        if not response.content:
            raise TTSProviderError(
                "TTS_EMPTY_AUDIO", "TTS provider returned no audio.", retryable=True
            )
        return response


class MiniMaxTTSProvider(_HTTPProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds, client=client)
        self.api_key, self.model = api_key, model

    async def synthesize(self, *, text: str, voice_id: str | None) -> TTSOutput:
        response = await self._request(
            "POST",
            "https://api.minimax.io/v1/t2a_v2",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "text": text,
                "stream": False,
                "voice_setting": {
                    "voice_id": voice_id or "male-qn-qingse",
                    "speed": 1.0,
                    "vol": 1.0,
                    "pitch": 0,
                },
                "audio_setting": {
                    "sample_rate": 32000,
                    "bitrate": 128000,
                    "format": "mp3",
                    "channel": 1,
                },
                "output_format": "hex",
                "language_boost": "auto",
            },
        )
        data = response.json()
        hex_audio = data.get("data", {}).get("audio")
        if not isinstance(hex_audio, str):
            raise TTSProviderError(
                "TTS_OUTPUT_INVALID", "MiniMax did not return audio data.", retryable=True
            )
        try:
            audio = bytes.fromhex(hex_audio)
        except ValueError as exc:
            raise TTSProviderError(
                "TTS_OUTPUT_INVALID", "MiniMax audio was invalid.", retryable=True
            ) from exc
        return TTSOutput(
            audio=audio,
            mime_type="audio/mpeg",
            extension="mp3",
            estimated_duration_seconds=_duration(text),
        )


class ElevenLabsTTSProvider(_HTTPProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_id: str,
        timeout_seconds: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds, client=client)
        self.api_key, self.base_url, self.model_id = api_key, base_url.rstrip("/"), model_id

    async def synthesize(self, *, text: str, voice_id: str | None) -> TTSOutput:
        if not voice_id:
            raise TTSProviderError(
                "TTS_VOICE_REQUIRED", "ElevenLabs requires a voice_id.", retryable=False
            )
        response = await self._request(
            "POST",
            f"{self.base_url}/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": self.api_key, "Accept": "audio/mpeg"},
            params={"output_format": "mp3_44100_128"},
            json={"text": text, "model_id": self.model_id},
        )
        return TTSOutput(
            audio=response.content,
            mime_type="audio/mpeg",
            extension="mp3",
            estimated_duration_seconds=_duration(text),
        )
