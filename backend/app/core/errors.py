from dataclasses import dataclass

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class AppError(Exception):
    status: int
    code: str
    title: str
    detail: str
    retryable: bool = False


def problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    retryable: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"https://errors.social-ops.local/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
            "request_id": str(request.state.request_id),
            "retryable": retryable,
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return problem_response(
        request,
        status=exc.status,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        retryable=exc.retryable,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}")
    return problem_response(
        request,
        status=422,
        code="VALIDATION_ERROR",
        title="Request validation failed",
        detail="; ".join(details),
    )
