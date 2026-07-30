import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
    require_owner,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import AIConnection, AIModelRoute
from app.modules.ai_connections.crypto import decrypt_api_key
from app.modules.ai_connections.schemas import (
    AIConnectionCreate,
    AIConnectionRead,
    AIConnectionTestRequest,
    AIConnectionTestResult,
    AIConnectionUpdate,
    AIModelRouteRead,
    AIModelRouteUpsert,
    AISettingsRead,
    AITaskType,
)
from app.modules.ai_connections.service import (
    connection_read,
    create_connection,
    provider_catalog,
    route_read,
    update_connection,
    upsert_route,
)
from app.providers.ai.base import AIProviderRequestError
from app.providers.ai.openai_compatible import OpenAICompatibleProvider
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/ai", tags=["ai-settings"])


def _connection(db: Session, workspace_id: uuid.UUID, connection_id: uuid.UUID) -> AIConnection:
    item = db.scalar(
        select(AIConnection).where(
            AIConnection.workspace_id == workspace_id,
            AIConnection.id == connection_id,
        )
    )
    if item is None:
        raise AppError(404, "NOT_FOUND", "AI connection not found", "AI connection not found.")
    return item


def _route_rows(
    db: Session,
    workspace_id: uuid.UUID,
) -> list[tuple[AIModelRoute, AIConnection]]:
    return list(
        db.execute(
            select(AIModelRoute, AIConnection)
            .join(AIConnection, AIConnection.id == AIModelRoute.connection_id)
            .where(AIModelRoute.workspace_id == workspace_id)
            .order_by(AIModelRoute.task_type)
        ).all()
    )


@router.get("/settings", response_model=DataResponse[AISettingsRead])
def get_ai_settings(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    connections = db.scalars(
        select(AIConnection)
        .where(AIConnection.workspace_id == context.workspace.id)
        .order_by(AIConnection.created_at, AIConnection.id)
    ).all()
    routes = _route_rows(db, context.workspace.id)
    return DataResponse(
        data=AISettingsRead(
            providers=provider_catalog(),
            connections=[connection_read(item) for item in connections],
            routes=[route_read(route, connection) for route, connection in routes],
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post("/connections", response_model=DataResponse[AIConnectionRead], status_code=201)
def add_ai_connection(
    body: AIConnectionCreate,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    try:
        connection = create_connection(
            db,
            workspace_id=context.workspace.id,
            body=body,
            settings=settings,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "AI connection name already exists",
            "Choose a unique connection name in this workspace.",
        ) from exc
    db.refresh(connection)
    return DataResponse(
        data=connection_read(connection),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.patch(
    "/connections/{connection_id}",
    response_model=DataResponse[AIConnectionRead],
)
def patch_ai_connection(
    connection_id: uuid.UUID,
    body: AIConnectionUpdate,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    connection = _connection(db, context.workspace.id, connection_id)
    try:
        update_connection(db, connection=connection, body=body, settings=settings)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "AI connection name already exists",
            "Choose a unique connection name in this workspace.",
        ) from exc
    db.refresh(connection)
    return DataResponse(
        data=connection_read(connection),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.put(
    "/routes/{task_type}",
    response_model=DataResponse[AIModelRouteRead],
)
def put_ai_route(
    task_type: AITaskType,
    body: AIModelRouteUpsert,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DataResponse:
    route = upsert_route(
        db,
        workspace_id=context.workspace.id,
        task_type=task_type,
        body=body,
    )
    connection = _connection(db, context.workspace.id, route.connection_id)
    db.commit()
    db.refresh(route)
    return DataResponse(
        data=route_read(route, connection),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/connections/{connection_id}/test",
    response_model=DataResponse[AIConnectionTestResult],
)
async def test_ai_connection(
    connection_id: uuid.UUID,
    body: AIConnectionTestRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_owner),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    connection = _connection(db, context.workspace.id, connection_id)
    api_key = decrypt_api_key(
        settings,
        workspace_id=context.workspace.id,
        connection_id=connection.id,
        encrypted_api_key=connection.encrypted_api_key,
    )
    if connection.provider in {"deepseek", "openai"} and not api_key:
        raise AppError(
            409,
            "AI_NOT_CONFIGURED",
            "AI API key is not configured",
            "Add an API key before testing this connection.",
        )
    selected_model = body.model
    if selected_model is None:
        selected_model = db.scalar(
            select(AIModelRoute.model)
            .where(
                AIModelRoute.workspace_id == context.workspace.id,
                AIModelRoute.connection_id == connection.id,
            )
            .order_by(AIModelRoute.task_type)
            .limit(1)
        )
    provider = OpenAICompatibleProvider(
        base_url=connection.base_url,
        api_key=api_key,
        model=selected_model or "connection-test",
        timeout_seconds=connection.timeout_seconds,
        json_mode=bool(connection.capabilities.get("json_mode", True)),
        temperature=0,
        max_tokens=256,
    )
    try:
        models, latency_ms = await provider.list_models()
    except AIProviderRequestError as exc:
        status = 401 if exc.code == "AI_AUTH_FAILED" else 503 if exc.retryable else 422
        raise AppError(
            status,
            exc.code,
            "AI connection test failed",
            exc.message,
            retryable=exc.retryable,
        ) from exc
    return DataResponse(
        data=AIConnectionTestResult(
            ok=True,
            provider=connection.provider,
            base_url=connection.base_url,
            latency_ms=latency_ms,
            available_models=models,
            requested_model_available=(
                selected_model in models if selected_model is not None else None
            ),
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
