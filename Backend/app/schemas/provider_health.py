from datetime import datetime

from pydantic import BaseModel


class ProviderHealthResponse(BaseModel):
    total_requests: int
    total_failures: int
    consecutive_failures: int
    last_success_at: datetime | None
    last_failure_at: datetime | None


class ProvidersHealthResponse(BaseModel):
    providers: dict[str, ProviderHealthResponse]
