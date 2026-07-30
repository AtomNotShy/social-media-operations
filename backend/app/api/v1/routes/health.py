import secrets

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.db.migration_state import expected_schema_revision
from app.db.models import ACTIVE_JOB_STATUSES, ProviderCircuitState, SyncJob
from app.modules.ai_connections.service import configured_for
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@router.get("/metrics", include_in_schema=False)
def metrics(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    if not settings.metrics_enabled:
        raise AppError(404, "NOT_FOUND", "Not found", "Metrics are disabled.")
    expected = settings.metrics_bearer_token
    if expected is not None:
        supplied = authorization.removeprefix("Bearer ") if authorization else ""
        if not secrets.compare_digest(supplied, expected.get_secret_value()):
            raise AppError(
                401,
                "UNAUTHENTICATED",
                "Authentication required",
                "A valid metrics bearer token is required.",
            )
    payload, content_type = request.app.state.metrics.render()
    return Response(content=payload, media_type=content_type)


@router.get("/health/ready")
def ready(
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "Service not ready",
            "The database is unavailable.",
            retryable=True,
        ) from exc
    if settings.app_env == "production":
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != expected_schema_revision():
            raise AppError(
                503,
                "SCHEMA_VERSION_MISMATCH",
                "Service not ready",
                "The database schema is not at the required revision.",
                retryable=True,
            )
    return {"status": "ok", "dependencies": {"database": "ok"}}


@router.get("/health/dependencies")
def dependencies(
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    queue_count = db.scalar(
        select(func.count(SyncJob.id)).where(
            SyncJob.workspace_id == context.workspace.id,
            SyncJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    )
    circuits = db.scalars(
        select(ProviderCircuitState).where(
            ProviderCircuitState.workspace_id == context.workspace.id
        )
    ).all()
    return DataResponse(
        data={
            "database": "ok",
            "queue": {"active_count": queue_count or 0},
            "tikhub": {
                "configured": bool(settings.tikhub_api_key),
                "open_circuits": [
                    {
                        "endpoint_key": item.endpoint_key,
                        "retry_after": item.retry_after,
                        "last_error_code": item.last_error_code,
                    }
                    for item in circuits
                    if item.state == "open"
                ],
            },
            "ai": {
                "configured": any(
                    configured_for(
                        db,
                        workspace_id=context.workspace.id,
                        task_type=task_type,
                        settings=settings,
                    )
                    for task_type in ("l1", "l2", "generation")
                ),
                "routes": {
                    task_type: configured_for(
                        db,
                        workspace_id=context.workspace.id,
                        task_type=task_type,
                        settings=settings,
                    )
                    for task_type in ("l1", "l2", "generation")
                },
            },
            "asr": {"provider": settings.asr_provider},
            "object_storage": {"provider": settings.object_storage_provider},
        },
        meta=ResponseMeta(request_id=request.state.request_id),
    )
