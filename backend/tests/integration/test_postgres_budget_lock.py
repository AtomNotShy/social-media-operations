import asyncio
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import ProviderUsageDaily, Workspace
from app.db.session import Database
from app.main import create_app
from app.providers.social.tikhub.client import TikHubResponse
from app.providers.social.tikhub.errors import TikHubError
from app.providers.social.tikhub.gateway import TikHubGateway
from app.providers.social.tikhub.registry import TikHubEndpoint

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 against a migrated test PostgreSQL database.",
)


class BlockingClient:
    def __init__(self, started: threading.Event, release: threading.Event) -> None:
        self.started = started
        self.release = release
        self.calls = 0

    async def request(self, endpoint, params):
        self.calls += 1
        self.started.set()
        await asyncio.to_thread(self.release.wait, 10)
        return TikHubResponse(
            payload={"code": 200, "data": {"params": params}},
            http_status=200,
            provider_code="200",
            provider_request_id="postgres-concurrency",
            latency_ms=1,
        )


def test_production_readiness_requires_current_postgres_schema():
    database_url = os.environ["DATABASE_URL"]
    settings = Settings(
        app_env="production",
        app_base_url="https://api.example.test",
        database_url=database_url,
        auth_mode="oidc",
        oidc_issuer="https://identity.example.test",
        oidc_audience="social-ops",
        oidc_jwks_url="https://identity.example.test/.well-known/jwks.json",
        allowed_origins=["https://app.example.test"],
        trusted_hosts=["api.example.test"],
        metrics_bearer_token="metrics-secret",
    )
    with TestClient(create_app(settings), base_url="https://api.example.test") as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "dependencies": {"database": "ok"}}


def test_workspace_row_lock_prevents_concurrent_budget_overspend():
    database_url = os.environ["DATABASE_URL"]
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("This integration test requires PostgreSQL.")
    database = Database(database_url)
    workspace_id = uuid.uuid4()
    with database.session_factory() as db:
        db.add(
            Workspace(
                id=workspace_id,
                name="PostgreSQL budget lock integration",
                timezone="UTC",
                daily_provider_budget_usd=Decimal("0.001"),
            )
        )
        db.commit()

    endpoint = TikHubEndpoint(
        key="integration.concurrent_budget",
        platform="xiaohongshu",
        path="/integration",
        version="test",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=0,
        max_attempts=1,
    )
    first_started = threading.Event()
    release_first = threading.Event()
    first_client = BlockingClient(first_started, release_first)
    second_client = BlockingClient(threading.Event(), threading.Event())
    second_client.release.set()

    def fetch(client, marker):
        async def run():
            with database.session_factory() as db:
                workspace = db.get(Workspace, workspace_id)
                try:
                    result = await TikHubGateway(db, client).fetch(
                        workspace=workspace,
                        endpoint=endpoint,
                        params={"marker": marker},
                    )
                    db.commit()
                    return ("success", result.cached)
                except TikHubError as exc:
                    db.rollback()
                    return ("error", exc.code)

        return asyncio.run(run())

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(fetch, first_client, "first")
            assert first_started.wait(10)
            second = pool.submit(fetch, second_client, "second")
            release_first.set()
            results = [first.result(timeout=15), second.result(timeout=15)]

        assert sorted(results) == [
            ("error", "PROVIDER_BUDGET_EXCEEDED"),
            ("success", False),
        ]
        assert first_client.calls + second_client.calls == 1
        with database.session_factory() as db:
            assert (
                db.scalar(
                    select(func.sum(ProviderUsageDaily.request_count)).where(
                        ProviderUsageDaily.workspace_id == workspace_id
                    )
                )
                == 1
            )
    finally:
        with database.session_factory() as db:
            workspace = db.get(Workspace, workspace_id)
            if workspace is not None:
                db.delete(workspace)
                db.commit()
        database.dispose()
