from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    job_type: str
    status: str
    priority: int
    attempt: int
    max_attempts: int
    run_after: datetime
    last_error_code: str | None
    last_error_message: str | None
    result: dict | None
    created_at: datetime
    finished_at: datetime | None
