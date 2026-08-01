import asyncio
from dataclasses import replace

import httpx
import pytest

from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.registry import get_endpoint


def test_client_sends_bearer_token_and_parses_success():
    seen_authorization = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"code": 200, "request_id": "request-1", "data": {}},
        )

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="secret-test-token",
                client=raw_client,
            )
            return await client.request(get_endpoint("xhs.profile"), {"user_id": "abc"})

    response = asyncio.run(run())

    assert seen_authorization == "Bearer secret-test-token"
    assert response.provider_request_id == "request-1"


def test_client_does_not_retry_authentication_failure():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"code": 401, "message": "invalid token"})

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="invalid-test-token",
                client=raw_client,
            )
            with pytest.raises(TikHubError) as captured:
                await client.request(get_endpoint("xhs.profile"), {"user_id": "abc"})
            return captured.value

    error = asyncio.run(run())

    assert calls == 1
    assert error.code == "PROVIDER_AUTHENTICATION_FAILED"
    assert error.retryable is False
    assert "invalid-test-token" not in repr(error)


def test_client_maps_payment_required_without_retaining_provider_payload():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            json={
                "detail": {
                    "headers": {"Authorization": "Bearer secret-test-token"},
                    "message": "payment required",
                }
            },
        )

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="secret-test-token",
                client=raw_client,
            )
            with pytest.raises(TikHubError) as captured:
                await client.request(get_endpoint("xhs.profile"), {"user_id": "abc"})
            return captured.value

    error = asyncio.run(run())

    assert error.code == "PROVIDER_PAYMENT_REQUIRED"
    assert error.retryable is False
    assert error.payload is None
    assert "secret-test-token" not in repr(error)


def test_client_retries_rate_limit_with_backoff():
    calls = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"code": 429})
        return httpx.Response(200, json={"code": 200, "data": {}})

    async def no_sleep(delay: float) -> None:
        delays.append(delay)

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="secret-test-token",
                client=raw_client,
                sleep=no_sleep,
            )
            endpoint = replace(get_endpoint("xhs.profile"), max_attempts=2)
            return await client.request(endpoint, {"user_id": "abc"})

    response = asyncio.run(run())

    assert response.http_status == 200
    assert calls == 2
    assert len(delays) == 1
