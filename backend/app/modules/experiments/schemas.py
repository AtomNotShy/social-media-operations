from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

EntityType = Literal[
    "inspirations",
    "tracked_profiles",
    "topics",
    "content_projects",
    "publish_plans",
    "reviews",
]


class SavedViewCreate(BaseModel):
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=255)
    query_params: dict = Field(default_factory=dict)
    is_shared: bool = False


class SavedViewUpdate(BaseModel):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    query_params: dict | None = None
    is_shared: bool | None = None


class SavedViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    entity_type: str
    name: str
    query_params: dict
    is_shared: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ExperimentVariant(BaseModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ExperimentCreate(BaseModel):
    owned_channel_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    hypothesis: str = Field(min_length=1, max_length=10000)
    primary_metric: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,64}$")
    variants: list[ExperimentVariant] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def unique_variant_keys(self) -> "ExperimentCreate":
        keys = [item.key for item in self.variants]
        if len(keys) != len(set(keys)):
            raise ValueError("experiment variant keys must be unique")
        return self


class ExperimentUpdate(BaseModel):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    hypothesis: str | None = Field(default=None, min_length=1, max_length=10000)
    primary_metric: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_.-]{1,64}$",
    )
    status: Literal["draft", "running", "completed", "cancelled"] | None = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owned_channel_id: UUID | None
    name: str
    hypothesis: str
    primary_metric: str
    variants: list[ExperimentVariant]
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    version: int
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class AssignmentCreate(BaseModel):
    content_project_id: UUID
    variant_key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    experiment_id: UUID
    content_project_id: UUID
    variant_key: str
    assigned_by: UUID | None
    created_at: datetime


class AttributionEventCreate(BaseModel):
    assignment_id: UUID
    publish_record_id: UUID | None = None
    event_type: Literal["exposure", "interaction", "conversion"]
    metric_name: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,64}$")
    value: Decimal = Field(ge=0)
    occurred_at: datetime
    source: Literal["manual", "platform_api", "analytics", "webhook"]
    source_ref: str = Field(min_length=1, max_length=2048)
    idempotency_key: str = Field(min_length=8, max_length=255)
    metadata: dict = Field(default_factory=dict)


class AttributionEventRead(BaseModel):
    id: UUID
    experiment_id: UUID
    assignment_id: UUID
    publish_record_id: UUID | None
    event_type: str
    metric_name: str
    value: Decimal
    occurred_at: datetime
    source: str
    source_ref: str
    idempotency_key: str
    metadata: dict
    created_at: datetime


class VariantMetricResult(BaseModel):
    variant_key: str
    assignment_count: int
    event_count: int
    total_value: Decimal
    evidence_event_ids: list[UUID]
    source_refs: list[str]


class ExperimentResultsRead(BaseModel):
    experiment_id: UUID
    experiment_version: int
    primary_metric: str
    generated_at: datetime
    variants: list[VariantMetricResult]
