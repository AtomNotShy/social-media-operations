from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisRun, GenerationRun
from app.modules.ai_connections.service import resolve_run_route
from app.providers.ai.fixture import FixtureAnalysisProvider
from app.providers.ai.gateway import AIGateway
from app.providers.ai.generation import FixtureContentGenerationProvider
from app.providers.ai.openai_compatible import OpenAICompatibleProvider


def _compatible_provider(route, *, idempotency_key: str | None = None):
    return OpenAICompatibleProvider(
        base_url=route.base_url or "",
        api_key=route.api_key,
        model=route.model,
        timeout_seconds=route.timeout_seconds,
        json_mode=route.json_mode,
        temperature=route.temperature,
        max_tokens=route.max_tokens,
        input_cost_per_million_usd=route.input_cost_per_million_usd,
        output_cost_per_million_usd=route.output_cost_per_million_usd,
        idempotency_key=idempotency_key,
    )


def _gateway_for(
    provider,
    *,
    db,
    route,
    settings: Settings,
    workspace_id,
):
    return AIGateway(
        provider,
        db=db,
        workspace_id=workspace_id,
        connection_id=route.connection_id,
        model=route.model,
        circuit_failure_threshold=settings.provider_circuit_failure_threshold,
        circuit_open_seconds=settings.provider_circuit_open_seconds,
        rate_limit_rpm=route.rate_limit_rpm,
    )


def analysis_provider_for_run(
    db: Session,
    *,
    run: AnalysisRun,
    settings: Settings,
):
    route = resolve_run_route(
        db,
        workspace_id=run.workspace_id,
        connection_id=run.ai_connection_id,
        model=run.model,
        task_type=run.analysis_level,
        settings=settings,
    )
    if route.provider == "fixture":
        return FixtureAnalysisProvider()
    idempotency_key = f"socialops:{run.workspace_id}:analysis:{run.id}"
    provider = _compatible_provider(route, idempotency_key=idempotency_key)
    return _gateway_for(
        provider,
        db=db,
        route=route,
        settings=settings,
        workspace_id=run.workspace_id,
    )


def generation_provider_for_run(
    db: Session,
    *,
    run: GenerationRun,
    settings: Settings,
):
    route = resolve_run_route(
        db,
        workspace_id=run.workspace_id,
        connection_id=run.ai_connection_id,
        model=run.model,
        task_type="generation",
        settings=settings,
    )
    if route.provider == "fixture":
        return FixtureContentGenerationProvider()
    idempotency_key = f"socialops:{run.workspace_id}:generation:{run.id}"
    provider = _compatible_provider(route, idempotency_key=idempotency_key)
    return _gateway_for(
        provider,
        db=db,
        route=route,
        settings=settings,
        workspace_id=run.workspace_id,
    )
