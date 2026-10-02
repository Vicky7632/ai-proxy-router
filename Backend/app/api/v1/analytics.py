from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cache_analytics import CacheAnalyticsResponse
from app.services.api_key_service import get_api_key
from app.services.cache_analytics_service import (
    get_cache_analytics,
    normalize_utc_datetime,
)

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/cache", response_model=CacheAnalyticsResponse)
def cache_analytics(
    from_datetime: datetime | None = Query(default=None, alias="from"),
    to_datetime: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _api_key=Depends(get_api_key),
) -> CacheAnalyticsResponse:
    normalized_from = normalize_utc_datetime(from_datetime)
    normalized_to = normalize_utc_datetime(to_datetime)
    if (
        normalized_from is not None
        and normalized_to is not None
        and normalized_from >= normalized_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'from' must be earlier than 'to'",
        )

    analytics = get_cache_analytics(
        db,
        from_datetime=normalized_from,
        to_datetime=normalized_to,
    )
    return CacheAnalyticsResponse(**asdict(analytics))
