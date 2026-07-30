from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

AIProviderName = Literal["deepseek", "openai", "openai_compatible"]
AITaskType = Literal["l1", "l2", "generation"]


class AIProviderCatalogItem(BaseModel):
    provider: AIProviderName
    label: str
    default_base_url: str | None
    suggested_models: list[str]
    custom_base_url: bool


class AIConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider: AIProviderName
    api_key: str | None = Field(default=None, max_length=4096)
    base_url: HttpUrl | None = None
    model: str = Field(min_length=1, max_length=128)
    use_for: list[AITaskType] = Field(default_factory=lambda: ["l1", "l2"])
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    json_mode: bool = True
    temperature: Decimal = Field(default=Decimal("0.2"), ge=0, le=2)
    max_tokens: int = Field(default=2000, ge=256, le=32768)
    input_cost_per_million_usd: Decimal = Field(default=Decimal("0"), ge=0)
    output_cost_per_million_usd: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def validate_connection(self) -> "AIConnectionCreate":
        if self.provider == "openai_compatible" and self.base_url is None:
            raise ValueError("base_url is required for openai_compatible")
        if self.provider in {"deepseek", "openai"} and not (self.api_key or "").strip():
            raise ValueError(f"api_key is required for {self.provider}")
        return self


class AIConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    base_url: HttpUrl | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    json_mode: bool | None = None


class AIConnectionRead(BaseModel):
    id: UUID
    name: str
    provider: str
    base_url: str
    enabled: bool
    timeout_seconds: int
    json_mode: bool
    api_key_configured: bool
    api_key_masked: str | None
    created_at: datetime
    updated_at: datetime


class AIModelRouteUpsert(BaseModel):
    connection_id: UUID
    model: str = Field(min_length=1, max_length=128)
    temperature: Decimal = Field(default=Decimal("0.2"), ge=0, le=2)
    max_tokens: int = Field(default=2000, ge=256, le=32768)
    input_cost_per_million_usd: Decimal = Field(default=Decimal("0"), ge=0)
    output_cost_per_million_usd: Decimal = Field(default=Decimal("0"), ge=0)


class AIModelRouteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_type: str
    connection_id: UUID
    connection_name: str
    provider: str
    model: str
    temperature: Decimal
    max_tokens: int
    input_cost_per_million_usd: Decimal
    output_cost_per_million_usd: Decimal
    configured: bool


class AISettingsRead(BaseModel):
    providers: list[AIProviderCatalogItem]
    connections: list[AIConnectionRead]
    routes: list[AIModelRouteRead]


class AIConnectionTestRequest(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=128)


class AIConnectionTestResult(BaseModel):
    ok: bool
    provider: str
    base_url: str
    latency_ms: int
    available_models: list[str]
    requested_model_available: bool | None
