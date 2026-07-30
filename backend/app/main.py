import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import router
from app.core.config import Settings, get_settings
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.logging import configure_logging
from app.core.metrics import AppMetrics
from app.db.models import AuditEvent
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings)
    logger = logging.getLogger("app.http")
    database = Database(app_settings.database_url)
    metrics = AppMetrics(database.session_factory)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database.dispose()

    application = FastAPI(
        title="社媒运营工作台 API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.database = database
    application.state.metrics = metrics

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        started_at = time.perf_counter()
        incoming = request.headers.get("X-Request-Id")
        try:
            request_id = uuid.UUID(incoming) if incoming else uuid.uuid4()
        except ValueError:
            request_id = uuid.uuid4()
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            duration_seconds = time.perf_counter() - started_at
            route = getattr(request.scope.get("route"), "path", "unmatched")
            metrics.observe_http(
                method=request.method,
                route=route,
                status_code=500,
                duration_seconds=duration_seconds,
            )
            logger.exception(
                "http_request_failed",
                extra={
                    "request_id": str(request_id),
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            raise
        response.headers["X-Request-Id"] = str(request_id)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            actor_user_id = getattr(request.state, "current_user_id", None)
            if actor_user_id is not None:
                path_parts = [part for part in request.url.path.split("/") if part]
                target_type = path_parts[2] if len(path_parts) > 2 else None
                target_id = None
                for part in reversed(path_parts):
                    try:
                        target_id = str(uuid.UUID(part))
                        break
                    except ValueError:
                        continue
                try:
                    with database.session_factory() as audit_db:
                        audit_db.add(
                            AuditEvent(
                                workspace_id=getattr(request.state, "workspace_id", None),
                                actor_user_id=actor_user_id,
                                request_id=request_id,
                                action=request.method,
                                path=request.url.path[:2048],
                                response_status=response.status_code,
                                target_type=target_type,
                                target_id=target_id,
                                metadata_json={},
                            )
                        )
                        audit_db.commit()
                except Exception:
                    metrics.audit_write_failures.inc()
                    logger.exception(
                        "audit_write_failed",
                        extra={
                            "request_id": str(request_id),
                            "method": request.method,
                            "path": request.url.path,
                        },
                    )
        duration_seconds = time.perf_counter() - started_at
        route = getattr(request.scope.get("route"), "path", "unmatched")
        metrics.observe_http(
            method=request.method,
            route=route,
            status_code=response.status_code,
            duration_seconds=duration_seconds,
        )
        logger.info(
            "http_request",
            extra={
                "request_id": str(request_id),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_seconds * 1000, 2),
            },
        )
        return response

    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    if app_settings.allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if app_settings.trusted_hosts:
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=app_settings.trusted_hosts,
        )
    application.include_router(router)
    return application


app = create_app()
