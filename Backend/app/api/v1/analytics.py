from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cache_analytics import CacheAnalyticsResponse
from app.services.api_key_service import get_api_key
from app.services.cache_analytics_service import get_cache_analytics

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/cache", response_model=CacheAnalyticsResponse)
def cache_analytics(
    db: Session = Depends(get_db),
    _api_key=Depends(get_api_key),
) -> CacheAnalyticsResponse:
    return CacheAnalyticsResponse(**asdict(get_cache_analytics(db)))
