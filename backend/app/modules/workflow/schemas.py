from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal[
    "douyin",
    "xiaohongshu",
    "youtube",
    "bilibili",
    "kuaishou",
    "weibo",
    "wechat_channels",
    "tiktok",
    "instagram",
    "x",
]


class OwnedChannelCreate(BaseModel):
    platform: Platform
    external_id: str | None = Field(default=None, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    positioning: str = Field(default="", max_length=10000)
    audience: dict = Field(default_factory=dict)
    content_pillars: list[str] = Field(default_factory=list, max_length=100)
    tone_rules: list[str] = Field(default_factory=list, max_length=100)
    prohibited_topics: list[str] = Field(default_factory=list, max_length=100)
    publishing_mode: Literal["manual", "official_api", "disabled"] = "manual"


class OwnedChannelUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    positioning: str | None = Field(default=None, max_length=10000)
    audience: dict | None = None
    content_pillars: list[str] | None = Field(default=None, max_length=100)
    tone_rules: list[str] | None = Field(default=None, max_length=100)
    prohibited_topics: list[str] | None = Field(default=None, max_length=100)
    publishing_mode: Literal["manual", "official_api", "disabled"] | None = None
    active: bool | None = None


class PositioningUpdate(BaseModel):
    positioning: str = Field(max_length=10000)
    audience: dict
    content_pillars: list[str] = Field(max_length=100)
    tone_rules: list[str] = Field(max_length=100)
    prohibited_topics: list[str] = Field(max_length=100)


class OwnedChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    external_id: str | None
    display_name: str
    handle: str | None
    bio: str | None
    avatar_url: str | None
    last_synced_at: datetime | None
    sync_status: str
    sync_error: str | None
    positioning: str
    audience: dict
    content_pillars: list
    tone_rules: list
    prohibited_topics: list
    publishing_mode: str
    active: bool
    created_at: datetime
    updated_at: datetime


class TopicCreate(BaseModel):
    owned_channel_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    audience_problem: str | None = Field(default=None, max_length=10000)
    angle: str | None = Field(default=None, max_length=10000)
    hook: str | None = Field(default=None, max_length=10000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    status: Literal["idea", "selected", "rejected", "archived"] = "idea"


class TopicUpdate(BaseModel):
    version: int = Field(ge=1)
    owned_channel_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    audience_problem: str | None = Field(default=None, max_length=10000)
    angle: str | None = Field(default=None, max_length=10000)
    hook: str | None = Field(default=None, max_length=10000)
    evidence_refs: list[str] | None = Field(default=None, max_length=100)
    status: Literal["idea", "selected", "rejected", "archived"] | None = None


class TopicFromInspiration(BaseModel):
    owned_channel_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    audience_problem: str | None = Field(default=None, max_length=10000)
    angle: str | None = Field(default=None, max_length=10000)
    hook: str | None = Field(default=None, max_length=10000)


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owned_channel_id: UUID | None
    title: str
    audience_problem: str | None
    angle: str | None
    hook: str | None
    evidence_refs: list
    status: str
    version: int
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ContentProjectCreate(BaseModel):
    topic_id: UUID | None = None
    owned_channel_id: UUID
    title: str = Field(min_length=1, max_length=500)
    owner_user_id: UUID | None = None
    due_at: datetime | None = None


class ContentProjectUpdate(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    owner_user_id: UUID | None = None
    due_at: datetime | None = None


class ProjectTransition(BaseModel):
    from_status: str = Field(alias="from", min_length=1, max_length=16)
    to_status: str = Field(alias="to", min_length=1, max_length=16)
    version: int = Field(ge=1)


class ContentProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    topic_id: UUID | None
    owned_channel_id: UUID
    title: str
    status: str
    owner_user_id: UUID | None
    due_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class ScriptCreate(BaseModel):
    project_version: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=100000)
    structured_body: dict | None = None
    change_note: str | None = Field(default=None, max_length=1000)


class ScriptDuplicate(BaseModel):
    project_version: int = Field(ge=1)
    change_note: str | None = Field(default=None, max_length=1000)


class ScriptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_project_id: UUID
    version_no: int
    body: str
    structured_body: dict | None
    created_by: UUID | None
    generation_run_id: UUID | None
    change_note: str | None
    created_at: datetime


class PublishPlanCreate(BaseModel):
    content_project_id: UUID
    owned_channel_id: UUID
    scheduled_at: datetime
    publishing_mode: Literal["manual", "official_api"] = "manual"
    publish_payload: dict


class PublishPlanUpdate(BaseModel):
    version: int = Field(ge=1)
    scheduled_at: datetime | None = None
    publish_payload: dict | None = None


class PublishPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_project_id: UUID
    owned_channel_id: UUID
    scheduled_at: datetime
    status: str
    publishing_mode: str
    publish_payload: dict
    approved_by: UUID | None
    approved_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class PublishPackage(BaseModel):
    plan_id: UUID
    plan_version: int
    project_id: UUID
    channel_id: UUID
    scheduled_at: datetime
    payload: dict
    latest_script: ScriptVersionRead
    assets: list[dict]
    publishing_mode: Literal["manual"]


class MarkPublishedRequest(BaseModel):
    version: int = Field(ge=1)
    published_url: str = Field(min_length=8, max_length=2048)
    published_at: datetime
    platform_content_id: str | None = Field(default=None, max_length=255)
    matched_publish_package: bool


class PublishRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    publish_plan_id: UUID
    platform_content_id: str | None
    published_url: str
    published_at: datetime
    result_payload: dict
    created_by: UUID | None
    created_at: datetime


class ReviewCreate(BaseModel):
    review_window: Literal["24h", "7d", "30d", "manual"]
    metrics: dict
    analysis: dict = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list, max_length=100)


class ReviewInsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    publish_record_id: UUID
    review_window: str
    metrics: dict
    analysis: dict
    next_actions: list
    created_by: UUID | None
    created_at: datetime


class AssetUploadIntentRequest(BaseModel):
    content_project_id: UUID | None = None
    asset_type: Literal["image", "video", "audio", "subtitle", "document"]
    mime_type: str = Field(min_length=3, max_length=255)
    size_bytes: int = Field(ge=1)
    checksum: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    source_type: Literal["uploaded", "generated", "reference"] = "uploaded"
    rights_note: str | None = Field(default=None, max_length=10000)


class AssetUploadIntentRead(BaseModel):
    intent_id: UUID
    upload_url: str
    upload_token: str
    storage_key: str
    expires_at: datetime
    required_headers: dict[str, str]


class AssetCompleteRequest(BaseModel):
    intent_id: UUID
    upload_token: str = Field(min_length=32, max_length=512)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_project_id: UUID | None
    asset_type: str
    storage_key: str
    mime_type: str
    size_bytes: int
    checksum: str
    source_type: str
    rights_note: str | None
    created_by: UUID | None
    created_at: datetime
