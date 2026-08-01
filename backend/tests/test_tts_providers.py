import asyncio
import json

import httpx

from app.providers.tts.providers import ElevenLabsTTSProvider, MiniMaxTTSProvider


def test_minimax_v2_request_uses_bearer_hex_output_and_no_group_id():
    seen: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": {"audio": "494433"}})

    async def synthesize():
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as client:
            provider = MiniMaxTTSProvider(
                api_key="minimax-key",
                model="speech-2.8-hd",
                timeout_seconds=10,
                client=client,
            )
            return await provider.synthesize(text="你好", voice_id="voice-1")

    output = asyncio.run(synthesize())
    assert seen["url"] == "https://api.minimax.io/v1/t2a_v2"
    assert seen["authorization"] == "Bearer minimax-key"
    assert seen["body"] == {
        "model": "speech-2.8-hd",
        "text": "你好",
        "stream": False,
        "voice_setting": {"voice_id": "voice-1", "speed": 1.0, "vol": 1.0, "pitch": 0},
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "output_format": "hex",
        "language_boost": "auto",
    }
    assert "group_id" not in seen["body"]
    assert output.audio == b"ID3"
    assert output.mime_type == "audio/mpeg"


def test_elevenlabs_output_format_is_a_query_parameter_not_json_body():
    seen: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("xi-api-key")
        seen["accept"] = request.headers.get("Accept")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"ID3audio", headers={"content-type": "audio/mpeg"})

    async def synthesize():
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as client:
            provider = ElevenLabsTTSProvider(
                api_key="eleven-key",
                base_url="https://api.elevenlabs.io",
                model_id="eleven_multilingual_v2",
                timeout_seconds=10,
                client=client,
            )
            return await provider.synthesize(text="Hello", voice_id="voice-1")

    output = asyncio.run(synthesize())
    assert seen["url"] == (
        "https://api.elevenlabs.io/v1/text-to-speech/voice-1?output_format=mp3_44100_128"
    )
    assert seen["api_key"] == "eleven-key"
    assert seen["accept"] == "audio/mpeg"
    assert seen["body"] == {"text": "Hello", "model_id": "eleven_multilingual_v2"}
    assert "output_format" not in seen["body"]
    assert output.audio == b"ID3audio"
