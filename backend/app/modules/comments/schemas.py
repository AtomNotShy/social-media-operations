from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommentFetchRequest(BaseModel):
    max_pages: int = Field(default=1, ge=1, le=3)
    sort_strategy: Literal["latest_v2"] = "latest_v2"


class CommentSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_comment_id: str
    parent_external_id: str | None
    author_snapshot: dict
    body_text: str
    like_count: int | None
    published_at: datetime | None
    captured_at: datetime
