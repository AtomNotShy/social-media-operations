import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import (
    ProviderCircuitState,
    ProviderFetch,
    ProviderUsageDaily,
    Workspace,
)
from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.registry import TikHubEndpoint


@dataclass(frozen=True, slots=True)
class GatewayResult:
    payload: dict[str, Any]
    provider_fetch_id: uuid.UUID
    cached: bool


def normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in sorted(params.items()) if value is not None and value != ""
    }


def request_fingerprint(
    *,
    workspace_id: uuid.UUID,
    endpoint: TikHubEndpoint,
    params: dict[str, Any],
) -> str:
    material = {
        "provider": "tikhub",
        "endpoint_key": endpoint.key,
        "endpoint_version": endpoint.version,
        "params": normalize_params(params),
        "workspace_id": str(workspace_id),
    }
    encoded = json.dumps(material, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


class TikHubGateway:
    def __init__(
        self,
        db: Session,
        client: TikHubHttpClient,
        *,
        circuit_failure_threshold: int = 5,
        circuit_open_seconds: int = 300,
    ) -> None:
        self.db = db
        self.client = client
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_open_seconds = circuit_open_seconds

    async def fetch(
        self,
        *,
        workspace: Workspace,
        endpoint: TikHubEndpoint,
        params: dict[str, Any],
        sync_job_id: uuid.UUID | None = None,
        force_refresh: bool = False,
    ) -> GatewayResult:
        locked_workspace = self.db.scalar(
            select(Workspace).where(Workspace.id == workspace.id).with_for_update()
        )
        if locked_workspace is None:
            raise TikHubError(
                code="NOT_FOUND",
                message="Workspace no longer exists.",
                retryable=False,
            )
        workspace = locked_workspace
        if bool((workspace.settings.get("external_calls") or {}).get("paused")):
            raise TikHubError(
                code="EXTERNAL_CALLS_PAUSED",
                message="External provider calls are paused for this workspace.",
                retryable=False,
            )
        normalized_params = normalize_params(params)
        fingerprint = request_fingerprint(
            workspace_id=workspace.id,
            endpoint=endpoint,
            params=normalized_params,
        )
        now = datetime.now(timezone.utc)
        cached = None if force_refresh else self.db.scalar(
            select(ProviderFetch)
            .where(
                ProviderFetch.workspace_id == workspace.id,
                ProviderFetch.request_fingerprint == fingerprint,
                ProviderFetch.error_code.is_(None),
                ProviderFetch.response_payload.is_not(None),
                ProviderFetch.fresh_until > now,
            )
            .order_by(ProviderFetch.fetched_at.desc())
            .limit(1)
        )
        if cached is not None and cached.response_payload is not None:
            return GatewayResult(
                payload=cached.response_payload,
                provider_fetch_id=cached.id,
                cached=True,
            )

        self._check_circuit(workspace, endpoint)
        self._enforce_budget(workspace, endpoint.estimated_cost_usd)
        try:
            response = await self.client.request(endpoint, normalized_params)
        except TikHubError as exc:
            fetch = ProviderFetch(
                workspace_id=workspace.id,
                sync_job_id=sync_job_id,
                provider="tikhub",
                platform=endpoint.platform,
                endpoint_key=endpoint.key,
                endpoint_path=endpoint.path,
                endpoint_version=endpoint.version,
                request_fingerprint=fingerprint,
                request_params_redacted=normalized_params,
                provider_request_id=exc.provider_request_id,
                http_status=exc.http_status,
                provider_code=exc.provider_code,
                latency_ms=exc.latency_ms,
                billable=False,
                estimated_cost_usd=Decimal("0"),
                # Provider error bodies are not persisted because upstream services may
                # echo request headers (including authorization credentials) in them.
                response_payload=None,
                fetched_at=now,
                error_code=exc.code,
            )
            self.db.add(fetch)
            self._record_failure(workspace, endpoint, exc)
            self.db.flush()
            raise

        fresh_until = now + timedelta(seconds=endpoint.freshness_seconds)
        fetch = ProviderFetch(
            workspace_id=workspace.id,
            sync_job_id=sync_job_id,
            provider="tikhub",
            platform=endpoint.platform,
            endpoint_key=endpoint.key,
            endpoint_path=endpoint.path,
            endpoint_version=endpoint.version,
            request_fingerprint=fingerprint,
            request_params_redacted=normalized_params,
            provider_request_id=response.provider_request_id,
            http_status=response.http_status,
            provider_code=response.provider_code,
            latency_ms=response.latency_ms,
            billable=True,
            estimated_cost_usd=endpoint.estimated_cost_usd,
            response_payload=response.payload,
            fetched_at=now,
            fresh_until=fresh_until,
        )
        self.db.add(fetch)
        self._record_success(workspace, endpoint)
        self._record_usage(workspace, endpoint)
        self.db.flush()
        return GatewayResult(
            payload=response.payload,
            provider_fetch_id=fetch.id,
            cached=False,
        )

    def _enforce_budget(self, workspace: Workspace, estimated_cost: Decimal) -> None:
        local_date = datetime.now(ZoneInfo(workspace.timezone)).date()
        used = self.db.scalar(
            select(func.coalesce(func.sum(ProviderUsageDaily.estimated_cost_usd), 0)).where(
                ProviderUsageDaily.workspace_id == workspace.id,
                ProviderUsageDaily.usage_date == local_date,
                ProviderUsageDaily.provider == "tikhub",
            )
        )
        if Decimal(used or 0) + estimated_cost > workspace.daily_provider_budget_usd:
            raise TikHubError(
                code="PROVIDER_BUDGET_EXCEEDED",
                message="The workspace daily TikHub budget has been reached.",
                retryable=False,
            )

    def _record_usage(self, workspace: Workspace, endpoint: TikHubEndpoint) -> None:
        local_date = datetime.now(ZoneInfo(workspace.timezone)).date()
        values = {
            "workspace_id": workspace.id,
            "usage_date": local_date,
            "provider": "tikhub",
            "endpoint_key": endpoint.key,
            "request_count": 1,
            "success_count": 1,
            "billable_count": 1,
            "estimated_cost_usd": endpoint.estimated_cost_usd,
        }
        dialect_name = self.db.get_bind().dialect.name
        insert_factory = {
            "postgresql": postgresql_insert,
            "sqlite": sqlite_insert,
        }.get(dialect_name)
        if insert_factory is not None:
            statement = insert_factory(ProviderUsageDaily).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=[
                    ProviderUsageDaily.workspace_id,
                    ProviderUsageDaily.usage_date,
                    ProviderUsageDaily.provider,
                    ProviderUsageDaily.endpoint_key,
                ],
                set_={
                    "request_count": ProviderUsageDaily.request_count + 1,
                    "success_count": ProviderUsageDaily.success_count + 1,
                    "billable_count": ProviderUsageDaily.billable_count + 1,
                    "estimated_cost_usd": (
                        ProviderUsageDaily.estimated_cost_usd + endpoint.estimated_cost_usd
                    ),
                },
            )
            self.db.execute(statement)
            return

        usage = self.db.scalar(
            select(ProviderUsageDaily)
            .where(
                ProviderUsageDaily.workspace_id == workspace.id,
                ProviderUsageDaily.usage_date == local_date,
                ProviderUsageDaily.provider == "tikhub",
                ProviderUsageDaily.endpoint_key == endpoint.key,
            )
            .with_for_update()
        )
        if usage is None:
            usage = ProviderUsageDaily(
                workspace_id=workspace.id,
                usage_date=local_date,
                provider="tikhub",
                endpoint_key=endpoint.key,
                request_count=0,
                success_count=0,
                billable_count=0,
                estimated_cost_usd=Decimal("0"),
            )
            self.db.add(usage)
        usage.request_count += 1
        usage.success_count += 1
        usage.billable_count += 1
        usage.estimated_cost_usd += endpoint.estimated_cost_usd

    def _get_or_create_circuit(
        self,
        workspace: Workspace,
        endpoint: TikHubEndpoint,
    ) -> ProviderCircuitState:
        circuit = self.db.scalar(
            select(ProviderCircuitState).where(
                ProviderCircuitState.workspace_id == workspace.id,
                ProviderCircuitState.provider == "tikhub",
                ProviderCircuitState.endpoint_key == endpoint.key,
            )
        )
        if circuit is None:
            circuit = ProviderCircuitState(
                workspace_id=workspace.id,
                provider="tikhub",
                endpoint_key=endpoint.key,
            )
            self.db.add(circuit)
            self.db.flush()
        return circuit

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def _check_circuit(
        self,
        workspace: Workspace,
        endpoint: TikHubEndpoint,
    ) -> None:
        circuit = self.db.scalar(
            select(ProviderCircuitState).where(
                ProviderCircuitState.workspace_id == workspace.id,
                ProviderCircuitState.provider == "tikhub",
                ProviderCircuitState.endpoint_key == endpoint.key,
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
            raise TikHubError(
                code="PROVIDER_CIRCUIT_OPEN",
                message="TikHub endpoint is temporarily circuit-broken.",
                retryable=True,
            )
        circuit.state = "half_open"
        self.db.flush()

    def _record_failure(
        self,
        workspace: Workspace,
        endpoint: TikHubEndpoint,
        error: TikHubError,
    ) -> None:
        if not error.retryable and error.code != "PROVIDER_AUTHENTICATION_FAILED":
            return
        now = datetime.now(timezone.utc)
        circuit = self._get_or_create_circuit(workspace, endpoint)
        circuit.consecutive_failures += 1
        circuit.last_failure_at = now
        circuit.last_error_code = error.code
        should_open = (
            error.code == "PROVIDER_AUTHENTICATION_FAILED"
            or circuit.state == "half_open"
            or circuit.consecutive_failures >= self.circuit_failure_threshold
        )
        if should_open:
            circuit.state = "open"
            circuit.opened_at = now
            circuit.retry_after = now + timedelta(seconds=self.circuit_open_seconds)

    def _record_success(
        self,
        workspace: Workspace,
        endpoint: TikHubEndpoint,
    ) -> None:
        circuit = self._get_or_create_circuit(workspace, endpoint)
        circuit.state = "closed"
        circuit.consecutive_failures = 0
        circuit.opened_at = None
        circuit.retry_after = None
        circuit.last_success_at = datetime.now(timezone.utc)
        circuit.last_error_code = None
