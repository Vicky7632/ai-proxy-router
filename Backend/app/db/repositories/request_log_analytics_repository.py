from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models.request_log import RequestLog


def get_cache_analytics_counts(db: Session) -> tuple[int, int, int, int, int, int]:
    row = db.query(
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
    ).one()
    return tuple(int(count) for count in row)
