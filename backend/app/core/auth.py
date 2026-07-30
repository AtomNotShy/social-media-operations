from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import Settings
from app.core.errors import AppError


@dataclass(frozen=True, slots=True)
class Identity:
    subject: str
    email: str | None = None
    display_name: str | None = None


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def authenticate_token(token: str, settings: Settings) -> Identity:
    if settings.auth_mode == "development":
        if not token.startswith("dev:") or not token.removeprefix("dev:").strip():
            raise AppError(
                401,
                "UNAUTHENTICATED",
                "Authentication required",
                "Use a development token in the form dev:<subject>.",
            )
        subject = token.removeprefix("dev:").strip()
        return Identity(subject=subject, display_name=subject)

    try:
        signing_key = _jwks_client(settings.oidc_jwks_url or "").get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except jwt.PyJWTError as exc:
        raise AppError(
            401,
            "UNAUTHENTICATED",
            "Authentication failed",
            "The access token is invalid or expired.",
        ) from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AppError(
            401,
            "UNAUTHENTICATED",
            "Authentication failed",
            "The access token does not contain a subject.",
        )
    return Identity(
        subject=subject,
        email=claims.get("email"),
        display_name=claims.get("name"),
    )
