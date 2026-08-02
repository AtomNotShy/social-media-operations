"""AI provider gateway: circuit breaker, per-connection rate limit, pause gate.

This mirrors the TikHub gateway contract so AI calls fail fast before real
money moves and recover automatically.  State lives in the shared
``provider_circuit_states`` table keyed by (workspace, "ai", connection:model),
so API, worker and future replicas observe the same breaker.

Network-level retries cannot be fully deduplicated against OpenAI-compatible
APIs, so every provider request also carries a stable ``Idempotency-Key`` built
from the logical run.  Providers that honor the header (OpenAI-compatible
convention) return the cached first response instead of billing a duplicate;
providers that ignore it simply process the retry.
"""

import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProviderCircuitState, Workspace
from app.providers.ai.base import (
    AIProviderRequestError,
    AnalysisProvider,
    AnalysisProviderResult,
)
from app.providers.ai.generation import GenerationProviderResult

_CIRCUIT_PROVIDER = "ai"
_CIRCUIT_OPENING_ERRORS = frozenset(
    {
        "AI_AUTH_FAILED",
        "AI_RATE_LIMITED",
        "AI_PROVIDER_TIMEOUT",
        "AI_PROVIDER_UNAVAILABLE",
    }
)


class _PerConnectionRateLimiter:
    """In-memory sliding-window limiter keyed by (workspace, connection).

    Documented limitation: the window is per process.  It is correct for the
    current single-worker deployment and becomes a Redis counter before the
    worker fleet scales out.
    """

    def __init__(self) -> None:
        self._windows: dict[tuple[uuid.UUID, uuid.UUID], deque[float]] = {}
        self._lock = Lock()

    def allow(self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID, rpm: int) -> bool:
        if rpm <= 0:
            return True
        key = (workspace_id, connection_id)
        now = time.monotonic()
        with self._lock:
            window = self._windows.setdefault(key, deque())
            while window and window[0] <= now - 60.0:
                window.popleft()
            if len(window) >= rpm:
                return False
            window.append(now)
            return True


class AIGateway:
    def __init__(
        self,
        provider: AnalysisProvider,
        *,
        db: Session,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID | None,
        model: str,
        circuit_failure_threshold: int = 5,
        circuit_open_seconds: int = 300,
        rate_limit_rpm: int = 0,
    ) -> None:
        self.provider = provider
        self.db = db
        self.workspace_id = workspace_id
        self.connection_id = connection_id
        self.model = model
        self.endpoint_key = (
            f"{connection_id}:{model}" if connection_id is not None else f"connectionless:{model}"
        )
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_open_seconds = circuit_open_seconds
        self.rate_limit_rpm = rate_limit_rpm

    async def analyze(self, **kwargs: object) -> AnalysisProviderResult:
        self._check_circuit()
        self._check_rate_limit()
        try:
            result = await self.provider.analyze(**kwargs)
        except AIProviderRequestError as exc:
            self._record_failure(exc)
            self.db.flush()
            raise
        self._record_success()
        self.db.flush()
        return result

    async def generate(self, **kwargs: object) -> GenerationProviderResult:
        self._check_circuit()
        self._check_rate_limit()
        try:
            result = await self.provider.generate(**kwargs)
        except AIProviderRequestError as exc:
            self._record_failure(exc)
            self.db.flush()
            raise
        self._record_success()
        self.db.flush()
        return result

    def _check_circuit(self) -> None:
        workspace = self.db.scalar(
            select(Workspace).where(Workspace.id == self.workspace_id)
        )
        if workspace is None:
            raise AIProviderRequestError(
                "AI_WORKSPACE_MISSING",
                "The AI run's workspace no longer exists.",
                retryable=False,
            )
        if bool((workspace.settings.get("external_calls") or {}).get("paused")):
            raise AIProviderRequestError(
                "AI_CALLS_PAUSED",
                "External provider calls are paused for this workspace.",
                retryable=False,
            )
        circuit = self.db.scalar(
            select(ProviderCircuitState).where(
                ProviderCircuitState.workspace_id == self.workspace_id,
                ProviderCircuitState.provider == _CIRCUIT_PROVIDER,
                ProviderCircuitState.endpoint_key == self.endpoint_key,
            )
        )
        if circuit is None or circuit.state == "closed":
            return
        now = datetime.now(timezone.utc)
        if (
            circuit.state == "open"
            and circuit.retry_after is not None
            and self._as_utc(circuit.retry_after) > now
        ):
            raise AIProviderRequestError(
                "AI_CIRCUIT_OPEN",
                "AI provider is temporarily circuit-broken.",
                retryable=True,
            )
        circuit.state = "half_open"
        self.db.flush()

    def _check_rate_limit(self) -> None:
        if self.connection_id is None or self.rate_limit_rpm <= 0:
            return
        if not _RATE_LIMITER.allow(
            workspace_id=self.workspace_id,
            connection_id=self.connection_id,
            rpm=self.rate_limit_rpm,
        ):
            raise AIProviderRequestError(
                "AI_RATE_LIMITED_LOCAL",
                "The configured per-connection rate limit was reached.",
                retryable=True,
            )

    def _get_or_create_circuit(self) -> ProviderCircuitState:
        circuit = self.db.scalar(
            select(ProviderCircuitState).where(
                ProviderCircuitState.workspace_id == self.workspace_id,
                ProviderCircuitState.provider == _CIRCUIT_PROVIDER,
                ProviderCircuitState.endpoint_key == self.endpoint_key,
            )
        )
        if circuit is None:
            circuit = ProviderCircuitState(
                workspace_id=self.workspace_id,
                provider=_CIRCUIT_PROVIDER,
                endpoint_key=self.endpoint_key,
            )
            self.db.add(circuit)
            self.db.flush()
        return circuit

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def _record_failure(self, error: AIProviderRequestError) -> None:
        if not error.retryable and error.code != "AI_AUTH_FAILED":
            return
        now = datetime.now(timezone.utc)
        circuit = self._get_or_create_circuit()
        circuit.consecutive_failures += 1
        circuit.last_failure_at = now
        circuit.last_error_code = error.code
        should_open = (
            error.code == "AI_AUTH_FAILED"
            or circuit.state == "half_open"
            or circuit.consecutive_failures >= self.circuit_failure_threshold
        )
        if should_open:
            circuit.state = "open"
            circuit.opened_at = now
            circuit.retry_after = now + timedelta(seconds=self.circuit_open_seconds)

    def _record_success(self) -> None:
        circuit = self._get_or_create_circuit()
        circuit.state = "closed"
        circuit.consecutive_failures = 0
        circuit.opened_at = None
        circuit.retry_after = None
        circuit.last_success_at = datetime.now(timezone.utc)
        circuit.last_error_code = None


_RATE_LIMITER = _PerConnectionRateLimiter()
