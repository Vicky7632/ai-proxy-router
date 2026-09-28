import asyncio
import calendar
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.api_key import APIKey
from app.db.models.provider import Provider
from app.db.models.request_log import RequestLog
from app.db.session import SessionLocal

COST_PRECISION = Decimal("0.00000001")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _next_month(value: datetime) -> datetime:
    month = value.month % 12 + 1
    year = value.year + (1 if month == 1 else 0)
    last_day = calendar.monthrange(year, month)[1]
    return value.replace(year=year, month=month, day=min(value.day, last_day))


def _apply_budget_reset(api_key: APIKey, now: datetime) -> None:
    if api_key.budget_reset_at is None:
        api_key.budget_reset_at = _next_month(now)
    elif api_key.budget_reset_at <= now:
        reset_at = api_key.budget_reset_at
        while reset_at <= now:
            reset_at = _next_month(reset_at)
        api_key.current_spend = 0.0
        api_key.budget_reset_at = reset_at


def _remaining_budget(api_key: APIKey) -> float | None:
    if api_key.budget_limit is None:
        return None
    return float(
        (
            Decimal(str(api_key.budget_limit))
            - Decimal(str(api_key.current_spend or 0))
        ).quantize(COST_PRECISION, rounding=ROUND_HALF_UP)
    )


def _check_budget_sync(api_key_id: UUID) -> float | None:
    db: Session = SessionLocal()
    try:
        api_key = (
            db.query(APIKey)
            .filter(APIKey.id == api_key_id)
            .with_for_update()
            .first()
        )
        if api_key is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")

        _apply_budget_reset(api_key, _utcnow())
        remaining = _remaining_budget(api_key)
        db.commit()
        if remaining is not None and remaining <= 0:
            raise HTTPException(status_code=403, detail="Monthly budget exceeded.")
        return remaining
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def check_budget(api_key: APIKey) -> float | None:
    return await asyncio.to_thread(_check_budget_sync, api_key.id)


def calculate_cost(
    provider: Provider,
    input_tokens: int,
    output_tokens: int,
) -> float:
    input_cost = (
        Decimal(str(input_tokens))
        / Decimal(1000)
        * Decimal(str(provider.cost_per_1k_input or 0))
    )
    output_cost = (
        Decimal(str(output_tokens))
        / Decimal(1000)
        * Decimal(str(provider.cost_per_1k_output or 0))
    )
    return float(
        (input_cost + output_cost).quantize(
            COST_PRECISION,
            rounding=ROUND_HALF_UP,
        )
    )


def update_spend(
    api_key_id: UUID,
    provider_name: str,
    input_tokens: int,
    output_tokens: int,
    request_log_id: UUID | None = None,
) -> float:
    db: Session = SessionLocal()
    try:
        provider = (
            db.query(Provider)
            .filter(Provider.name == provider_name)
            .first()
        )
        if provider is None:
            raise ValueError(f"Provider '{provider_name}' is not configured")
        api_key = (
            db.query(APIKey)
            .filter(APIKey.id == api_key_id)
            .with_for_update()
            .first()
        )
        if api_key is None:
            raise ValueError(f"API key '{api_key_id}' no longer exists")

        _apply_budget_reset(api_key, _utcnow())
        cost = calculate_cost(provider, input_tokens, output_tokens)
        api_key.current_spend = float(
            (
                Decimal(str(api_key.current_spend or 0))
                + Decimal(str(cost))
            ).quantize(COST_PRECISION, rounding=ROUND_HALF_UP)
        )
        if request_log_id is not None:
            request_log = (
                db.query(RequestLog)
                .filter(RequestLog.id == request_log_id)
                .first()
            )
            if request_log is None:
                raise ValueError(f"Request log '{request_log_id}' does not exist")
            request_log.cost = cost
        db.commit()
        return cost
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
