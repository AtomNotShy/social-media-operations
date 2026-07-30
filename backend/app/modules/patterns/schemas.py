from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PatternStatus = Literal["draft", "validated", "retired"]


class PatternCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=10000)
    pattern_type: str = Field(min_length=1, max_length=32)
    applicable_channels: list[UUID] = Field(default_factory=list, max_length=100)
    source_content_ids: list[UUID] = Field(default_factory=list, max_length=100)
    evidence: dict = Field(default_factory=dict)


class PatternUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    pattern_type: str | None = Field(default=None, min_length=1, max_length=32)
    applicable_channels: list[UUID] | None = Field(default=None, max_length=100)
    source_content_ids: list[UUID] | None = Field(default=None, max_length=100)
    evidence: dict | None = None


class PatternRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    pattern_type: str
    applicable_channels: list
    source_content_ids: list
    evidence: dict
    status: PatternStatus
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
