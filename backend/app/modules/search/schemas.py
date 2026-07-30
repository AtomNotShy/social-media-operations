from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

SearchEntityType = Literal["inspiration", "pattern", "topic", "content_project"]


class UnifiedSearchResult(BaseModel):
    entity_type: SearchEntityType
    entity_id: UUID
    title: str
    snippet: str | None
    matched_fields: list[str]
    source_ref: str
    updated_at: datetime
