from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TikHubError(Exception):
    code: str
    message: str
    retryable: bool
    http_status: int | None = None
    provider_code: str | None = None
    provider_request_id: str | None = None
    latency_ms: int | None = None
    payload: dict[str, Any] | None = field(default=None, repr=False)


def map_status(status: int) -> tuple[str, bool]:
    if status in {401, 403}:
        return "PROVIDER_AUTHENTICATION_FAILED", False
    if status == 402:
        return "PROVIDER_PAYMENT_REQUIRED", False
    if status == 404:
        return "SOURCE_CONTENT_UNAVAILABLE", False
    if status == 422:
        return "PROVIDER_REQUEST_INVALID", False
    if status == 429:
        return "PROVIDER_RATE_LIMITED", True
    if status >= 500:
        return "PROVIDER_UNAVAILABLE", True
    return "PROVIDER_ERROR", False
