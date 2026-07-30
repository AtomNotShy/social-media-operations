from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel


class ResponseMeta(BaseModel):
    request_id: UUID
    next_cursor: str | None = None


DataT = TypeVar("DataT")


class DataResponse(BaseModel, Generic[DataT]):
    data: DataT
    meta: ResponseMeta


class JobAccepted(BaseModel):
    job_id: UUID
    status: str
