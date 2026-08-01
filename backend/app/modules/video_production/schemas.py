from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VideoRenderSpec(BaseModel):
    width: int = Field(default=1080, ge=320, le=3840)
    height: int = Field(default=1920, ge=320, le=3840)
    fps: int = Field(default=30, ge=24, le=60)
    style: str = Field(default="dark-tech", min_length=1, max_length=64)


class VideoRunCreate(BaseModel):
    script_version_id: UUID
    tts_provider: Literal["minimax", "elevenlabs", "fixture"] | None = None
    voice_id: str | None = Field(default=None, max_length=255)
    render_spec: VideoRenderSpec = Field(default_factory=VideoRenderSpec)
    instruction: str | None = Field(default=None, max_length=4000)
    force: bool = False


class VideoRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_project_id: UUID
    script_version_id: UUID
    sync_job_id: UUID | None
    status: str
    tts_provider: str
    voice_id: str | None
    render_spec: dict
    result: dict | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class VideoRunAccepted(BaseModel):
    video_run: VideoRunRead
    reused: bool
