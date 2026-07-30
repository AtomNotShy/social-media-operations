import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(**overrides):
    values = {
        "app_env": "production",
        "app_base_url": "https://api.example.com",
        "database_url": "postgresql+psycopg://user:pass@db.example.com/app",
        "auth_mode": "oidc",
        "oidc_issuer": "https://identity.example.com",
        "oidc_audience": "social-ops",
        "oidc_jwks_url": "https://identity.example.com/.well-known/jwks.json",
        "allowed_origins": ["https://app.example.com"],
        "trusted_hosts": ["api.example.com"],
        "metrics_bearer_token": "metrics-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_production_configuration_is_accepted():
    settings = production_settings()

    assert settings.app_env == "production"
    assert settings.trusted_hosts == ["api.example.com"]


def test_s3_storage_requires_bucket():
    with pytest.raises(ValidationError, match="OBJECT_STORAGE_BUCKET"):
        Settings(
            app_env="test",
            auth_mode="development",
            database_url="sqlite:///:memory:",
            object_storage_provider="s3",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("app_base_url", "http://api.example.com", "APP_BASE_URL"),
        ("database_url", "sqlite:///production.db", "DATABASE_URL"),
        ("allowed_origins", [], "ALLOWED_ORIGINS"),
        ("allowed_origins", ["*"], "ALLOWED_ORIGINS"),
        ("allowed_origins", ["http://app.example.com"], "ALLOWED_ORIGINS"),
        ("trusted_hosts", [], "TRUSTED_HOSTS"),
        ("trusted_hosts", ["*"], "TRUSTED_HOSTS"),
        ("metrics_bearer_token", None, "METRICS_BEARER_TOKEN"),
        ("metrics_bearer_token", "", "METRICS_BEARER_TOKEN"),
    ],
)
def test_insecure_production_configuration_is_rejected(field, value, message):
    with pytest.raises(ValidationError, match=message):
        production_settings(**{field: value})
