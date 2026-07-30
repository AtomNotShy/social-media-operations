from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_subject: str
    email: str | None
    display_name: str
    status: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = "Australia/Melbourne"
    daily_provider_budget_usd: Decimal = Field(default=Decimal("5"), ge=0)
    daily_ai_budget_usd: Decimal = Field(default=Decimal("5"), ge=0)

    @field_validator("timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = None
    daily_provider_budget_usd: Decimal | None = Field(default=None, ge=0)
    daily_ai_budget_usd: Decimal | None = Field(default=None, ge=0)
    settings: dict | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_exist(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    timezone: str
    daily_provider_budget_usd: Decimal
    daily_ai_budget_usd: Decimal
    settings: dict
    created_at: datetime
    updated_at: datetime


class ExternalCallsPauseRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ExternalCallsStateRead(BaseModel):
    paused: bool
    reason: str | None
    changed_at: datetime
    changed_by: UUID


class MeRead(BaseModel):
    user: UserRead
    memberships: list["MembershipRead"]


class MembershipRead(BaseModel):
    workspace_id: UUID
    role: str


class WorkspaceMemberAdd(BaseModel):
    user_id: UUID
    role: Literal["owner", "editor", "viewer"]


class WorkspaceMemberUpdate(BaseModel):
    role: Literal["owner", "editor", "viewer"]


class WorkspaceMemberRead(BaseModel):
    id: UUID
    user: UserRead
    role: str
    created_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID | None
    actor_user_id: UUID | None
    request_id: UUID
    action: str
    path: str
    response_status: int
    target_type: str | None
    target_id: str | None
    metadata_json: dict
    created_at: datetime
