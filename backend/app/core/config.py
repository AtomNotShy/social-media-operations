from decimal import Decimal
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_base_url: str = "http://127.0.0.1:8000"
    database_url: str = "postgresql+psycopg://social:social@127.0.0.1:5432/social_ops"
    auth_mode: Literal["development", "oidc"] = "development"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    allowed_origins: list[str] = Field(default_factory=list)
    trusted_hosts: list[str] = Field(default_factory=list)
    default_timezone: str = "Australia/Melbourne"
    log_level: str = "INFO"
    log_json: bool = False
    metrics_enabled: bool = True
    metrics_bearer_token: SecretStr | None = None
    tikhub_base_url: str = "https://api.tikhub.io"
    tikhub_api_key: str | None = None
    job_lock_timeout_seconds: int = Field(default=300, ge=30, le=86400)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
    scheduler_poll_seconds: float = Field(default=30.0, ge=1, le=3600)
    ai_provider: str = "disabled"
    ai_model: str = "disabled"
    ai_prompt_version: str = "l1-v1"
    ai_l1_estimated_cost_usd: Decimal = Field(default=Decimal("0.05"), ge=0)
    ai_l2_estimated_cost_usd: Decimal = Field(default=Decimal("0.20"), ge=0)
    ai_generation_estimated_cost_usd: Decimal = Field(default=Decimal("0.15"), ge=0)
    ai_credentials_encryption_key: SecretStr | None = None
    ai_credentials_key_file: str = "storage/config/.credentials.key"
    asr_provider: str = "disabled"
    asr_model: str = "disabled"
    asr_estimated_cost_usd: Decimal = Field(default=Decimal("0.10"), ge=0)
    video_tts_provider: str = "disabled"
    video_tts_timeout_seconds: int = Field(default=60, ge=5, le=600)
    minimax_api_key: SecretStr | None = None
    # Retained only so existing local .env files continue loading; current v2 TTS does not use it.
    minimax_group_id: str | None = None
    minimax_tts_model: str = "speech-2.8-hd"
    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_voice_id: str | None = None
    video_runs_dir: str = "storage/video-runs"
    video_codex_bin: str = "codex"
    video_codex_timeout_seconds: int = Field(default=900, ge=30, le=7200)
    video_hyperframes_bin: str = "npx"
    video_hyperframes_timeout_seconds: int = Field(default=900, ge=30, le=7200)
    object_storage_provider: str = "disabled"
    object_storage_bucket: str | None = None
    object_storage_region: str = "ap-southeast-2"
    object_storage_endpoint_url: str | None = None
    object_storage_access_key_id: str | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_session_token: SecretStr | None = None
    object_storage_addressing_style: Literal["auto", "path", "virtual"] = "auto"
    max_asset_size_bytes: int = Field(default=500_000_000, ge=1_000_000, le=5_000_000_000)
    provider_circuit_failure_threshold: int = Field(default=5, ge=1, le=100)
    provider_circuit_open_seconds: int = Field(default=300, ge=10, le=86400)
    provider_payload_retention_days: int = Field(default=90, ge=7, le=3650)
    failed_provider_payload_retention_days: int = Field(default=30, ge=1, le=3650)
    unpromoted_content_retention_days: int = Field(default=30, ge=1, le=3650)

    @field_validator("tikhub_base_url", mode="before")
    @classmethod
    def normalize_tikhub_base_url(cls, value: object) -> str:
        if value is None or not str(value).strip():
            return "https://api.tikhub.io"
        normalized = str(value).strip().rstrip("/")
        if not normalized.startswith("https://"):
            raise ValueError("TIKHUB_BASE_URL must use HTTPS")
        return normalized

    @field_validator("metrics_bearer_token", mode="before")
    @classmethod
    def normalize_metrics_bearer_token(cls, value: object) -> str | None:
        if value is None:
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        return raw.strip() or None

    @field_validator("ai_credentials_encryption_key", mode="before")
    @classmethod
    def normalize_ai_credentials_encryption_key(cls, value: object) -> str | None:
        if value is None:
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        return raw.strip() or None

    @model_validator(mode="after")
    def validate_auth_configuration(self) -> "Settings":
        if self.auth_mode == "development" and self.app_env not in {"local", "test"}:
            raise ValueError("development authentication is only allowed in local/test")
        if self.auth_mode == "oidc":
            missing = [
                name
                for name, value in (
                    ("OIDC_ISSUER", self.oidc_issuer),
                    ("OIDC_AUDIENCE", self.oidc_audience),
                    ("OIDC_JWKS_URL", self.oidc_jwks_url),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"OIDC authentication requires: {', '.join(missing)}")
        providers = (
            ("AI_PROVIDER", self.ai_provider, {"disabled", "fixture"}),
            ("ASR_PROVIDER", self.asr_provider, {"disabled", "fixture"}),
            (
                "VIDEO_TTS_PROVIDER",
                self.video_tts_provider,
                {"disabled", "fixture", "minimax", "elevenlabs"},
            ),
            (
                "OBJECT_STORAGE_PROVIDER",
                self.object_storage_provider,
                {"disabled", "fixture", "s3"},
            ),
        )
        for name, value, supported in providers:
            if value not in supported:
                raise ValueError(f"{name} provider '{value}' is not implemented")
            if value == "fixture" and self.app_env != "test":
                raise ValueError(f"{name}=fixture is only allowed in the test environment")
        if self.object_storage_provider == "s3" and not self.object_storage_bucket:
            raise ValueError("OBJECT_STORAGE_BUCKET is required when OBJECT_STORAGE_PROVIDER=s3")
        if self.video_tts_provider == "fixture" and self.app_env != "test":
            raise ValueError("VIDEO_TTS_PROVIDER=fixture is only allowed in the test environment")
        if self.video_tts_provider == "minimax" and self.minimax_api_key is None:
            raise ValueError("MiniMax TTS requires MINIMAX_API_KEY")
        if self.video_tts_provider == "elevenlabs" and self.elevenlabs_api_key is None:
            raise ValueError("ElevenLabs TTS requires ELEVENLABS_API_KEY")
        if self.app_env == "production":
            if urlparse(self.app_base_url).scheme != "https":
                raise ValueError("APP_BASE_URL must use HTTPS in production")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("DATABASE_URL must use PostgreSQL in production")
            if not self.allowed_origins:
                raise ValueError("ALLOWED_ORIGINS must be configured in production")
            invalid_origins = [
                origin
                for origin in self.allowed_origins
                if origin == "*" or urlparse(origin).scheme != "https"
            ]
            if invalid_origins:
                raise ValueError("ALLOWED_ORIGINS must contain HTTPS origins without wildcards")
            if not self.trusted_hosts or "*" in self.trusted_hosts:
                raise ValueError("TRUSTED_HOSTS must be configured without wildcards in production")
            if self.metrics_enabled and self.metrics_bearer_token is None:
                raise ValueError(
                    "METRICS_BEARER_TOKEN is required when metrics are enabled in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
