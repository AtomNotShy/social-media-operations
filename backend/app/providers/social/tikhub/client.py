import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from app.providers.social.tikhub.errors import TikHubError, map_status
from app.providers.social.tikhub.registry import TikHubEndpoint


@dataclass(frozen=True, slots=True)
class TikHubResponse:
    payload: dict[str, Any]
    http_status: int
    provider_code: str | None
    provider_request_id: str | None
    latency_ms: int


class TikHubHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError("TikHub API key is required")
        self._headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
            "User-Agent": "social-ops-backend/0.1",
        }
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            follow_redirects=False,
        )
        self._sleep = sleep

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        endpoint: TikHubEndpoint,
        params: dict[str, Any],
    ) -> TikHubResponse:
        last_error: TikHubError | None = None
        for attempt in range(1, endpoint.max_attempts + 1):
            started = perf_counter()
            try:
                response = await self._client.get(
                    endpoint.path,
                    params=params,
                    headers=self._headers,
                    timeout=endpoint.timeout_seconds,
                )
                latency_ms = round((perf_counter() - started) * 1000)
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise TikHubError(
                        code="PROVIDER_SCHEMA_INCOMPATIBLE",
                        message="TikHub returned a non-JSON response.",
                        retryable=False,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                    ) from exc
                if not isinstance(payload, dict):
                    raise TikHubError(
                        code="PROVIDER_SCHEMA_INCOMPATIBLE",
                        message="TikHub returned an unexpected response shape.",
                        retryable=False,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                    )

                provider_code_value = payload.get("code")
                provider_code = (
                    str(provider_code_value) if provider_code_value is not None else None
                )
                provider_request_id = payload.get("request_id")
                effective_status = response.status_code
                if response.is_success and provider_code not in {None, "200"}:
                    try:
                        effective_status = int(provider_code or response.status_code)
                    except ValueError:
                        effective_status = 500
                if not response.is_success or provider_code not in {None, "200"}:
                    code, retryable = map_status(effective_status)
                    last_error = TikHubError(
                        code=code,
                        message="TikHub request failed.",
                        retryable=retryable,
                        http_status=response.status_code,
                        provider_code=provider_code,
                        provider_request_id=provider_request_id,
                        latency_ms=latency_ms,
                        payload=payload,
                    )
                    if retryable and attempt < endpoint.max_attempts:
                        await self._backoff(attempt)
                        continue
                    raise last_error

                return TikHubResponse(
                    payload=payload,
                    http_status=response.status_code,
                    provider_code=provider_code,
                    provider_request_id=provider_request_id,
                    latency_ms=latency_ms,
                )
            except httpx.RequestError as exc:
                latency_ms = round((perf_counter() - started) * 1000)
                last_error = TikHubError(
                    code="PROVIDER_UNAVAILABLE",
                    message="TikHub could not be reached.",
                    retryable=True,
                    latency_ms=latency_ms,
                )
                if attempt < endpoint.max_attempts:
                    await self._backoff(attempt)
                    continue
                raise last_error from exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("TikHub request loop exited unexpectedly")

    async def _backoff(self, attempt: int) -> None:
        delay = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.25)
        await self._sleep(delay)
