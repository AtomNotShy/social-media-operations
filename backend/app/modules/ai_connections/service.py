import ipaddress
import socket
import uuid
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import AIConnection, AIModelRoute
from app.modules.ai_connections.crypto import decrypt_api_key, encrypt_api_key
from app.modules.ai_connections.pricing import (
    PRICING_CATALOG_VERSION,
    PRICING_SOURCE_URL,
    effective_route_prices,
    official_model_prices,
    official_price_for,
)
from app.modules.ai_connections.schemas import (
    AIConnectionCreate,
    AIConnectionRead,
    AIConnectionUpdate,
    AIModelRouteRead,
    AIModelRouteUpsert,
    AIProviderCatalogItem,
    AIProviderModelPricing,
)

DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
}
TASK_TYPES = ("l1", "l2", "generation")


@dataclass(frozen=True, slots=True)
class ResolvedAIRoute:
    connection_id: uuid.UUID | None
    provider: str
    model: str
    base_url: str | None
    api_key: str | None
    timeout_seconds: int
    json_mode: bool
    temperature: Decimal
    max_tokens: int
    input_cost_per_million_usd: Decimal
    output_cost_per_million_usd: Decimal
    rate_limit_rpm: int = 0


def provider_catalog() -> list[AIProviderCatalogItem]:
    model_pricing = [
        AIProviderModelPricing(
            model=item.model,
            input_cost_per_million_usd=item.input_cost_per_million_usd,
            output_cost_per_million_usd=item.output_cost_per_million_usd,
            cache_hit_input_cost_per_million_usd=item.cache_hit_input_cost_per_million_usd,
            currency=item.currency,
            recommended_max_tokens=item.recommended_max_tokens,
            notes=item.notes,
        )
        for item in official_model_prices()
    ]
    return [
        AIProviderCatalogItem(
            provider="deepseek",
            label="DeepSeek",
            default_base_url=DEFAULT_BASE_URLS["deepseek"],
            suggested_models=["deepseek-v4-flash", "deepseek-v4-pro"],
            custom_base_url=False,
            model_pricing=model_pricing,
            pricing_source_url=PRICING_SOURCE_URL,
            pricing_catalog_version=PRICING_CATALOG_VERSION,
        ),
        AIProviderCatalogItem(
            provider="openai",
            label="OpenAI",
            default_base_url=DEFAULT_BASE_URLS["openai"],
            suggested_models=[],
            custom_base_url=False,
        ),
        AIProviderCatalogItem(
            provider="openai_compatible",
            label="OpenAI-Compatible",
            default_base_url=None,
            suggested_models=[],
            custom_base_url=True,
        ),
    ]


def _validate_base_url(base_url: str, settings: Settings) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Invalid AI provider URL",
            "AI provider base_url must be an absolute HTTP(S) URL.",
        )
    if settings.app_env in {"staging", "production"} and parsed.scheme != "https":
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "HTTPS is required",
            "AI provider base_url must use HTTPS outside local development.",
        )
    if settings.app_env in {"staging", "production"}:
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
            }
        except socket.gaierror as exc:
            raise AppError(
                422,
                "AI_PROVIDER_HOST_INVALID",
                "AI provider host cannot be resolved",
                "The configured AI provider hostname could not be resolved.",
            ) from exc
        if any(
            ipaddress.ip_address(address).is_private
            or ipaddress.ip_address(address).is_loopback
            or ipaddress.ip_address(address).is_link_local
            for address in addresses
        ):
            raise AppError(
                422,
                "AI_PROVIDER_HOST_INVALID",
                "Private AI provider host is not allowed",
                "Use a public HTTPS provider endpoint outside local development.",
            )
    return normalized


def connection_read(connection: AIConnection) -> AIConnectionRead:
    return AIConnectionRead(
        id=connection.id,
        name=connection.name,
        provider=connection.provider,
        base_url=connection.base_url,
        enabled=connection.enabled,
        timeout_seconds=connection.timeout_seconds,
        json_mode=bool(connection.capabilities.get("json_mode", True)),
        api_key_configured=connection.encrypted_api_key is not None,
        api_key_masked=(
            f"••••{connection.api_key_last_four}" if connection.api_key_last_four else None
        ),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def create_connection(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    body: AIConnectionCreate,
    settings: Settings,
) -> AIConnection:
    connection_id = uuid.uuid4()
    if body.provider in DEFAULT_BASE_URLS and body.base_url is not None:
        supplied_base_url = str(body.base_url).strip().rstrip("/")
        if supplied_base_url != DEFAULT_BASE_URLS[body.provider]:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Official provider URL cannot be overridden",
                "Use openai_compatible for a custom API base URL.",
            )
    base_url = _validate_base_url(
        str(body.base_url) if body.base_url is not None else DEFAULT_BASE_URLS[body.provider],
        settings,
    )
    api_key = (body.api_key or "").strip() or None
    connection = AIConnection(
        id=connection_id,
        workspace_id=workspace_id,
        name=body.name.strip(),
        provider=body.provider,
        base_url=base_url,
        encrypted_api_key=(
            encrypt_api_key(
                settings,
                workspace_id=workspace_id,
                connection_id=connection_id,
                api_key=api_key,
            )
            if api_key
            else None
        ),
        api_key_last_four=api_key[-4:] if api_key else None,
        enabled=True,
        timeout_seconds=body.timeout_seconds,
        capabilities={"json_mode": body.json_mode},
    )
    db.add(connection)
    db.flush()
    for task_type in dict.fromkeys(body.use_for):
        upsert_route(
            db,
            workspace_id=workspace_id,
            task_type=task_type,
            body=AIModelRouteUpsert(
                connection_id=connection.id,
                model=body.model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                input_cost_per_million_usd=body.input_cost_per_million_usd,
                output_cost_per_million_usd=body.output_cost_per_million_usd,
            ),
        )
    return connection


def update_connection(
    db: Session,
    *,
    connection: AIConnection,
    body: AIConnectionUpdate,
    settings: Settings,
) -> AIConnection:
    if body.name is not None:
        connection.name = body.name.strip()
    if body.base_url is not None:
        if connection.provider != "openai_compatible":
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Base URL cannot be changed",
                "DeepSeek and OpenAI use their approved official base URLs.",
            )
        connection.base_url = _validate_base_url(str(body.base_url), settings)
    if body.enabled is not None:
        connection.enabled = body.enabled
    if body.timeout_seconds is not None:
        connection.timeout_seconds = body.timeout_seconds
    if body.json_mode is not None:
        connection.capabilities = {
            **connection.capabilities,
            "json_mode": body.json_mode,
        }
    if body.clear_api_key:
        connection.encrypted_api_key = None
        connection.api_key_last_four = None
    elif body.api_key is not None and body.api_key.strip():
        api_key = body.api_key.strip()
        connection.encrypted_api_key = encrypt_api_key(
            settings,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
            api_key=api_key,
        )
        connection.api_key_last_four = api_key[-4:]
    db.flush()
    return connection


def upsert_route(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_type: str,
    body: AIModelRouteUpsert,
) -> AIModelRoute:
    if task_type not in TASK_TYPES:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Unsupported AI task type",
            f"task_type must be one of: {', '.join(TASK_TYPES)}.",
        )
    connection = db.scalar(
        select(AIConnection).where(
            AIConnection.id == body.connection_id,
            AIConnection.workspace_id == workspace_id,
        )
    )
    if connection is None:
        raise AppError(404, "NOT_FOUND", "AI connection not found", "AI connection not found.")
    route = db.scalar(
        select(AIModelRoute).where(
            AIModelRoute.workspace_id == workspace_id,
            AIModelRoute.task_type == task_type,
        )
    )
    if route is None:
        route = AIModelRoute(
            workspace_id=workspace_id,
            task_type=task_type,
            connection_id=connection.id,
        )
        db.add(route)
    official = official_price_for(connection.provider, body.model)
    if official is not None:
        # Official providers/models are priced by the built-in catalog; the
        # operator cannot type prices for DeepSeek official models.  Custom
        # OpenAI-compatible endpoints keep their own prices below.
        input_price = official.input_cost_per_million_usd
        output_price = official.output_cost_per_million_usd
    else:
        input_price = body.input_cost_per_million_usd
        output_price = body.output_cost_per_million_usd
    route.connection_id = connection.id
    route.model = body.model.strip()
    route.temperature = body.temperature
    route.max_tokens = body.max_tokens
    route.input_cost_per_million_usd = input_price
    route.output_cost_per_million_usd = output_price
    db.flush()
    return route


def route_read(route: AIModelRoute, connection: AIConnection) -> AIModelRouteRead:
    input_price, output_price = effective_route_prices(
        provider=connection.provider,
        model=route.model,
        stored_input_cost_per_million_usd=route.input_cost_per_million_usd,
        stored_output_cost_per_million_usd=route.output_cost_per_million_usd,
    )
    return AIModelRouteRead(
        task_type=route.task_type,
        connection_id=connection.id,
        connection_name=connection.name,
        provider=connection.provider,
        model=route.model,
        temperature=route.temperature,
        max_tokens=route.max_tokens,
        input_cost_per_million_usd=input_price,
        output_cost_per_million_usd=output_price,
        configured=connection.enabled
        and (
            connection.encrypted_api_key is not None
            or connection.provider == "openai_compatible"
        ),
    )


def resolve_route(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_type: str,
    settings: Settings,
    include_secret: bool,
) -> ResolvedAIRoute:
    if settings.ai_provider == "fixture" and settings.ai_model != "disabled":
        return ResolvedAIRoute(
            connection_id=None,
            provider="fixture",
            model=settings.ai_model,
            base_url=None,
            api_key=None,
            timeout_seconds=30,
            json_mode=True,
            temperature=Decimal("0"),
            max_tokens=2000,
            input_cost_per_million_usd=Decimal("0"),
            output_cost_per_million_usd=Decimal("0"),
        )
    row = db.execute(
        select(AIModelRoute, AIConnection)
        .join(AIConnection, AIConnection.id == AIModelRoute.connection_id)
        .where(
            AIModelRoute.workspace_id == workspace_id,
            AIModelRoute.task_type == task_type,
        )
    ).one_or_none()
    if row is None:
        raise AppError(
            409,
            "AI_NOT_CONFIGURED",
            "AI model route is not configured",
            f"Configure an AI connection and select a model for {task_type}.",
        )
    route, connection = row
    if not connection.enabled:
        raise AppError(
            409,
            "AI_CONNECTION_DISABLED",
            "AI connection is disabled",
            f"Enable the AI connection selected for {task_type}.",
        )
    if connection.provider in {"deepseek", "openai"} and not connection.encrypted_api_key:
        raise AppError(
            409,
            "AI_NOT_CONFIGURED",
            "AI API key is not configured",
            f"Add an API key to the {connection.name} connection.",
        )
    api_key = (
        decrypt_api_key(
            settings,
            workspace_id=workspace_id,
            connection_id=connection.id,
            encrypted_api_key=connection.encrypted_api_key,
        )
        if include_secret
        else None
    )
    if include_secret and connection.provider in {"deepseek", "openai"} and not api_key:
        raise AppError(
            409,
            "AI_NOT_CONFIGURED",
            "AI API key is not configured",
            f"Add an API key to the {connection.name} connection.",
        )
    input_price, output_price = effective_route_prices(
        provider=connection.provider,
        model=route.model,
        stored_input_cost_per_million_usd=route.input_cost_per_million_usd,
        stored_output_cost_per_million_usd=route.output_cost_per_million_usd,
    )
    return ResolvedAIRoute(
        connection_id=connection.id,
        provider=connection.provider,
        model=route.model,
        base_url=connection.base_url,
        api_key=api_key,
        timeout_seconds=connection.timeout_seconds,
        json_mode=bool(connection.capabilities.get("json_mode", True)),
        temperature=route.temperature,
        max_tokens=route.max_tokens,
        input_cost_per_million_usd=input_price,
        output_cost_per_million_usd=output_price,
        rate_limit_rpm=int(connection.capabilities.get("rate_limit_rpm", 0) or 0),
    )


def resolve_run_route(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID | None,
    model: str,
    task_type: str,
    settings: Settings,
) -> ResolvedAIRoute:
    if connection_id is None and settings.ai_provider == "fixture":
        return resolve_route(
            db,
            workspace_id=workspace_id,
            task_type=task_type,
            settings=settings,
            include_secret=True,
        )
    connection = db.scalar(
        select(AIConnection).where(
            AIConnection.id == connection_id,
            AIConnection.workspace_id == workspace_id,
        )
    )
    if connection is None or not connection.enabled:
        raise AppError(
            409,
            "AI_CONNECTION_UNAVAILABLE",
            "AI connection is unavailable",
            "The AI connection selected when this job was created is missing or disabled.",
        )
    route = db.scalar(
        select(AIModelRoute).where(
            AIModelRoute.workspace_id == workspace_id,
            AIModelRoute.task_type == task_type,
            AIModelRoute.connection_id == connection.id,
        )
    )
    api_key = decrypt_api_key(
        settings,
        workspace_id=workspace_id,
        connection_id=connection.id,
        encrypted_api_key=connection.encrypted_api_key,
    )
    if connection.provider in {"deepseek", "openai"} and not api_key:
        raise AppError(
            409,
            "AI_NOT_CONFIGURED",
            "AI API key is not configured",
            f"Add an API key to the {connection.name} connection.",
        )
    input_price, output_price = effective_route_prices(
        provider=connection.provider,
        model=model,
        stored_input_cost_per_million_usd=(
            route.input_cost_per_million_usd if route is not None else Decimal("0")
        ),
        stored_output_cost_per_million_usd=(
            route.output_cost_per_million_usd if route is not None else Decimal("0")
        ),
    )
    return ResolvedAIRoute(
        connection_id=connection.id,
        provider=connection.provider,
        model=model,
        base_url=connection.base_url,
        api_key=api_key,
        timeout_seconds=connection.timeout_seconds,
        json_mode=bool(connection.capabilities.get("json_mode", True)),
        temperature=route.temperature if route is not None else Decimal("0.2"),
        max_tokens=route.max_tokens if route is not None else 2000,
        input_cost_per_million_usd=input_price,
        output_cost_per_million_usd=output_price,
        rate_limit_rpm=int(connection.capabilities.get("rate_limit_rpm", 0) or 0),
    )


def configured_for(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    task_type: str,
    settings: Settings,
) -> bool:
    try:
        resolve_route(
            db,
            workspace_id=workspace_id,
            task_type=task_type,
            settings=settings,
            include_secret=False,
        )
    except AppError:
        return False
    return True
