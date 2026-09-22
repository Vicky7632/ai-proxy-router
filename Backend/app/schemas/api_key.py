from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    created_at: datetime
    revoked_at: datetime | None


class APIKeyCreateResponse(APIKeyResponse):
    api_key: str
