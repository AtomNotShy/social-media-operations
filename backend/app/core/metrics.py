from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from sqlalchemy import case, func, select

from app.db.models import (
    ACTIVE_JOB_STATUSES,
    AICostLedger,
    ProcessHeartbeat,
    ProviderCircuitState,
    ProviderFetch,
    ProviderUsageDaily,
    SyncJob,
    Workspace,
)


class DatabaseMetricsCollector:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def collect(self):
        jobs = GaugeMetricFamily(
            "social_ops_jobs",
            "Current jobs by type and status.",
            labels=["job_type", "status"],
        )
        oldest = GaugeMetricFamily(
            "social_ops_job_oldest_active_seconds",
            "Age in seconds of the oldest active job by type.",
            labels=["job_type"],
        )
        provider_requests = GaugeMetricFamily(
            "social_ops_provider_requests_24h",
            "Provider requests observed in the last 24 hours.",
            labels=["provider", "endpoint", "outcome"],
        )
        provider_cost = GaugeMetricFamily(
            "social_ops_provider_estimated_cost_usd_24h",
            "Estimated billable provider cost in USD for the last 24 hours.",
            labels=["provider", "endpoint"],
        )
        provider_errors = GaugeMetricFamily(
            "social_ops_provider_errors_24h",
            "Provider errors observed in the last 24 hours.",
            labels=["provider", "endpoint", "error_code"],
        )
        circuits = GaugeMetricFamily(
            "social_ops_provider_circuits",
            "Provider circuit count by provider and state.",
            labels=["provider", "state"],
        )
        ai_cost = GaugeMetricFamily(
            "social_ops_ai_effective_cost_usd_24h",
            "Reserved or settled AI/ASR cost in USD created in the last 24 hours.",
            labels=["provider", "resource_type", "status"],
        )
        provider_budget_ratio = GaugeMetricFamily(
            "social_ops_provider_budget_utilization_ratio",
            "Current local-day provider budget utilization by workspace.",
            labels=["workspace_id"],
        )
        ai_budget_ratio = GaugeMetricFamily(
            "social_ops_ai_budget_utilization_ratio",
            "Current local-day AI and ASR budget utilization by workspace.",
            labels=["workspace_id"],
        )
        process_heartbeat_age = GaugeMetricFamily(
            "social_ops_process_heartbeat_age_seconds",
            "Seconds since a worker or scheduler instance last reported a heartbeat.",
            labels=["service", "instance_id"],
        )
        collection_success = GaugeMetricFamily(
            "social_ops_database_metrics_collection_success",
            "Whether the latest database metrics collection succeeded.",
        )
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        try:
            with self.session_factory() as db:
                for job_type, job_status, count in db.execute(
                    select(SyncJob.job_type, SyncJob.status, func.count(SyncJob.id))
                    .group_by(SyncJob.job_type, SyncJob.status)
                    .order_by(SyncJob.job_type, SyncJob.status)
                ):
                    jobs.add_metric([job_type, job_status], count)
                for job_type, created_at in db.execute(
                    select(SyncJob.job_type, func.min(SyncJob.created_at))
                    .where(SyncJob.status.in_(ACTIVE_JOB_STATUSES))
                    .group_by(SyncJob.job_type)
                ):
                    if created_at is not None:
                        aware = (
                            created_at
                            if created_at.tzinfo is not None
                            else created_at.replace(tzinfo=timezone.utc)
                        )
                        oldest.add_metric(
                            [job_type],
                            max(0, (now - aware).total_seconds()),
                        )
                outcome = case(
                    (ProviderFetch.error_code.is_(None), "success"),
                    else_="error",
                )
                for provider, endpoint, result, count in db.execute(
                    select(
                        ProviderFetch.provider,
                        ProviderFetch.endpoint_key,
                        outcome,
                        func.count(ProviderFetch.id),
                    )
                    .where(ProviderFetch.fetched_at >= cutoff)
                    .group_by(
                        ProviderFetch.provider,
                        ProviderFetch.endpoint_key,
                        outcome,
                    )
                ):
                    provider_requests.add_metric([provider, endpoint, result], count)
                for provider, endpoint, cost in db.execute(
                    select(
                        ProviderFetch.provider,
                        ProviderFetch.endpoint_key,
                        func.coalesce(func.sum(ProviderFetch.estimated_cost_usd), 0),
                    )
                    .where(
                        ProviderFetch.fetched_at >= cutoff,
                        ProviderFetch.billable.is_(True),
                    )
                    .group_by(ProviderFetch.provider, ProviderFetch.endpoint_key)
                ):
                    provider_cost.add_metric([provider, endpoint], float(cost or 0))
                for provider, endpoint, error_code, count in db.execute(
                    select(
                        ProviderFetch.provider,
                        ProviderFetch.endpoint_key,
                        ProviderFetch.error_code,
                        func.count(ProviderFetch.id),
                    )
                    .where(
                        ProviderFetch.fetched_at >= cutoff,
                        ProviderFetch.error_code.is_not(None),
                    )
                    .group_by(
                        ProviderFetch.provider,
                        ProviderFetch.endpoint_key,
                        ProviderFetch.error_code,
                    )
                ):
                    provider_errors.add_metric(
                        [provider, endpoint, error_code],
                        count,
                    )
                for provider, circuit_state, count in db.execute(
                    select(
                        ProviderCircuitState.provider,
                        ProviderCircuitState.state,
                        func.count(ProviderCircuitState.id),
                    ).group_by(
                        ProviderCircuitState.provider,
                        ProviderCircuitState.state,
                    )
                ):
                    circuits.add_metric([provider, circuit_state], count)
                effective_cost = case(
                    (
                        AICostLedger.status == "settled",
                        func.coalesce(
                            AICostLedger.actual_cost_usd,
                            AICostLedger.estimated_cost_usd,
                        ),
                    ),
                    else_=AICostLedger.estimated_cost_usd,
                )
                for provider, resource_type, ledger_status, cost in db.execute(
                    select(
                        AICostLedger.provider,
                        AICostLedger.resource_type,
                        AICostLedger.status,
                        func.coalesce(func.sum(effective_cost), Decimal("0")),
                    )
                    .where(AICostLedger.created_at >= cutoff)
                    .group_by(
                        AICostLedger.provider,
                        AICostLedger.resource_type,
                        AICostLedger.status,
                    )
                ):
                    ai_cost.add_metric(
                        [provider, resource_type, ledger_status],
                        float(cost or 0),
                    )
                for workspace in db.scalars(select(Workspace)).all():
                    local_date = datetime.now(ZoneInfo(workspace.timezone)).date()
                    provider_used = db.scalar(
                        select(
                            func.coalesce(
                                func.sum(ProviderUsageDaily.estimated_cost_usd),
                                Decimal("0"),
                            )
                        ).where(
                            ProviderUsageDaily.workspace_id == workspace.id,
                            ProviderUsageDaily.usage_date == local_date,
                        )
                    )
                    ai_used = db.scalar(
                        select(func.coalesce(func.sum(effective_cost), Decimal("0"))).where(
                            AICostLedger.workspace_id == workspace.id,
                            AICostLedger.usage_date == local_date,
                            AICostLedger.status.in_(("reserved", "settled", "uncertain")),
                        )
                    )
                    provider_budget_ratio.add_metric(
                        [str(workspace.id)],
                        (
                            float(Decimal(provider_used or 0) / workspace.daily_provider_budget_usd)
                            if workspace.daily_provider_budget_usd > 0
                            else (1 if Decimal(provider_used or 0) > 0 else 0)
                        ),
                    )
                    ai_budget_ratio.add_metric(
                        [str(workspace.id)],
                        (
                            float(Decimal(ai_used or 0) / workspace.daily_ai_budget_usd)
                            if workspace.daily_ai_budget_usd > 0
                            else (1 if Decimal(ai_used or 0) > 0 else 0)
                        ),
                    )
                for heartbeat in db.scalars(select(ProcessHeartbeat)).all():
                    heartbeat_at = (
                        heartbeat.heartbeat_at
                        if heartbeat.heartbeat_at.tzinfo is not None
                        else heartbeat.heartbeat_at.replace(tzinfo=timezone.utc)
                    )
                    process_heartbeat_age.add_metric(
                        [heartbeat.service, heartbeat.instance_id],
                        max(0, (now - heartbeat_at).total_seconds()),
                    )
            collection_success.add_metric([], 1)
        except Exception:
            collection_success.add_metric([], 0)
        yield jobs
        yield oldest
        yield provider_requests
        yield provider_cost
        yield provider_errors
        yield circuits
        yield ai_cost
        yield provider_budget_ratio
        yield ai_budget_ratio
        yield process_heartbeat_age
        yield collection_success


class AppMetrics:
    def __init__(self, session_factory=None) -> None:
        self.registry = CollectorRegistry()
        self.http_requests = Counter(
            "social_ops_http_requests_total",
            "Total HTTP requests handled by the API.",
            ("method", "route", "status_code"),
            registry=self.registry,
        )
        self.http_request_duration = Histogram(
            "social_ops_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ("method", "route"),
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry,
        )
        self.audit_write_failures = Counter(
            "social_ops_audit_write_failures_total",
            "Total audit event persistence failures.",
            registry=self.registry,
        )
        if session_factory is not None:
            self.registry.register(DatabaseMetricsCollector(session_factory))

    def observe_http(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        self.http_requests.labels(
            method=method,
            route=route,
            status_code=str(status_code),
        ).inc()
        self.http_request_duration.labels(method=method, route=route).observe(duration_seconds)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
