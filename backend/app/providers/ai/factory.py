from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisRun, GenerationRun
from app.modules.ai_connections.service import resolve_run_route
from app.providers.ai.fixture import FixtureAnalysisProvider
from app.providers.ai.generation import FixtureContentGenerationProvider
from app.providers.ai.openai_compatible import OpenAICompatibleProvider


def _compatible_provider(route):
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
    return FixtureAnalysisProvider() if route.provider == "fixture" else _compatible_provider(route)


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
    return (
        FixtureContentGenerationProvider()
        if route.provider == "fixture"
        else _compatible_provider(route)
    )
