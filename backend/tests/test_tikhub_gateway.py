import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models import (
    ProviderCircuitState,
    ProviderFetch,
    ProviderUsageDaily,
    Workspace,
)
from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.registry import TikHubEndpoint, get_endpoint


def test_gateway_reuses_fresh_response_without_second_charge(app, workspace):
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"code": 200, "request_id": "cache-test", "data": {}},
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
            with app.state.database.session_factory() as db:
                current_workspace = db.get(Workspace, uuid.UUID(workspace["id"]))
                gateway = TikHubGateway(db, client)
                first = await gateway.fetch(
                    workspace=current_workspace,
                    endpoint=get_endpoint("xhs.profile"),
                    params={"user_id": "cache-profile"},
                )
                db.commit()
                second = await gateway.fetch(
                    workspace=current_workspace,
                    endpoint=get_endpoint("xhs.profile"),
                    params={"user_id": "cache-profile"},
                )
                db.commit()
                return first, second

    first, second = asyncio.run(run())

    assert first.cached is False
    assert second.cached is True
    assert first.provider_fetch_id == second.provider_fetch_id
    assert calls == 1
    with app.state.database.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProviderFetch)) == 1
        usage = db.scalar(select(ProviderUsageDaily))
        assert usage.request_count == 1


def test_gateway_blocks_request_before_exceeding_workspace_budget(app, workspace):
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"code": 200, "data": {}})

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
            with app.state.database.session_factory() as db:
                current_workspace = db.get(Workspace, uuid.UUID(workspace["id"]))
                current_workspace.daily_provider_budget_usd = Decimal("0")
                db.commit()
                with pytest.raises(TikHubError) as captured:
                    await TikHubGateway(db, client).fetch(
                        workspace=current_workspace,
                        endpoint=get_endpoint("xhs.profile"),
                        params={"user_id": "budget-profile"},
                    )
                return captured.value

    error = asyncio.run(run())

    assert error.code == "PROVIDER_BUDGET_EXCEEDED"
    assert calls == 0


def test_gateway_honors_workspace_external_call_emergency_stop(app, workspace):
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"code": 200, "data": {}})

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
            with app.state.database.session_factory() as db:
                current_workspace = db.get(Workspace, uuid.UUID(workspace["id"]))
                current_workspace.settings = {
                    "external_calls": {
                        "paused": True,
                        "reason": "Incident drill",
                    }
                }
                db.commit()
                with pytest.raises(TikHubError) as captured:
                    await TikHubGateway(db, client).fetch(
                        workspace=current_workspace,
                        endpoint=get_endpoint("xhs.profile"),
                        params={"user_id": "paused-profile"},
                    )
                return captured.value

    error = asyncio.run(run())

    assert error.code == "EXTERNAL_CALLS_PAUSED"
    assert calls == 0


def test_gateway_records_failed_call_without_marking_it_billable(app, workspace):
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"code": 401, "message": "invalid token", "request_id": "failed-request"},
        )

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
            with app.state.database.session_factory() as db:
                current_workspace = db.get(Workspace, uuid.UUID(workspace["id"]))
                with pytest.raises(TikHubError):
                    await TikHubGateway(db, client).fetch(
                        workspace=current_workspace,
                        endpoint=get_endpoint("xhs.profile"),
                        params={"user_id": "failed-profile"},
                    )
                db.commit()

    asyncio.run(run())

    with app.state.database.session_factory() as db:
        fetch = db.scalar(select(ProviderFetch))
        assert fetch.error_code == "PROVIDER_AUTHENTICATION_FAILED"
        assert fetch.billable is False
        assert fetch.estimated_cost_usd == 0
        assert db.scalar(select(func.count()).select_from(ProviderUsageDaily)) == 0


def test_gateway_opens_circuit_and_recovers_after_cooldown(
    client,
    app,
    auth_headers,
    workspace,
):
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 2:
            return httpx.Response(503, json={"code": 503, "message": "unavailable"})
        return httpx.Response(200, json={"code": 200, "data": {}})

    endpoint = TikHubEndpoint(
        key="xhs.circuit_fixture",
        platform="xiaohongshu",
        path="/fixture",
        version="test",
        estimated_cost_usd=Decimal("0"),
        freshness_seconds=0,
        max_attempts=1,
    )

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="test",
                client=raw_client,
            )
            with app.state.database.session_factory() as db:
                current_workspace = db.get(Workspace, uuid.UUID(workspace["id"]))
                gateway = TikHubGateway(
                    db,
                    provider_client,
                    circuit_failure_threshold=2,
                    circuit_open_seconds=60,
                )
                for _ in range(2):
                    with pytest.raises(TikHubError) as failed:
                        await gateway.fetch(
                            workspace=current_workspace,
                            endpoint=endpoint,
                            params={"query": "same"},
                        )
                    assert failed.value.code == "PROVIDER_UNAVAILABLE"
                    db.commit()
                with pytest.raises(TikHubError) as blocked:
                    await gateway.fetch(
                        workspace=current_workspace,
                        endpoint=endpoint,
                        params={"query": "same"},
                    )
                assert blocked.value.code == "PROVIDER_CIRCUIT_OPEN"
                assert calls == 2
                circuit = db.scalar(select(ProviderCircuitState))
                circuit.retry_after = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.commit()
                result = await gateway.fetch(
                    workspace=current_workspace,
                    endpoint=endpoint,
                    params={"query": "same"},
                )
                db.commit()
                assert result.cached is False

    asyncio.run(run())
    assert calls == 3
    with app.state.database.session_factory() as db:
        circuit = db.scalar(select(ProviderCircuitState))
        assert circuit.state == "closed"
        assert circuit.consecutive_failures == 0
        assert circuit.last_success_at is not None

    health = client.get(
        "/api/v1/system/provider-health",
        headers={**auth_headers, "X-Workspace-Id": workspace["id"]},
    )
    assert health.status_code == 200
    endpoint_health = health.json()["data"]["endpoints"][0]
    assert endpoint_health["request_count_24h"] == 3
    assert endpoint_health["success_count_24h"] == 1
    assert endpoint_health["failure_count_24h"] == 2
    assert endpoint_health["circuit"]["state"] == "closed"
