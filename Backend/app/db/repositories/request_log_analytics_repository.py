from datetime import datetime

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models.request_log import RequestLog


def get_cache_analytics_counts(
    db: Session,
    from_datetime: datetime | None = None,
    to_datetime: datetime | None = None,
) -> tuple[int, int, int, int, int, int]:
    query = db.query(
        func.count(RequestLog.id),
        func.count(
            case(
                (RequestLog.redis_cache_status == "hit", RequestLog.id),
            )
        ),
        func.count(
            case(
                (RequestLog.redis_cache_status == "miss", RequestLog.id),
            )
        ),
        func.count(
            case(
                (RequestLog.semantic_cache_status == "hit", RequestLog.id),
            )
        ),
        func.count(
            case(
                (RequestLog.semantic_cache_status == "miss", RequestLog.id),
            )
        ),
        func.count(
            case(
                (RequestLog.provider_called.is_(True), RequestLog.id),
            )
        ),
    )
    if from_datetime is not None:
        query = query.filter(RequestLog.created_at >= from_datetime)
    if to_datetime is not None:
        query = query.filter(RequestLog.created_at < to_datetime)

    row = query.one()
    return tuple(int(count) for count in row)
