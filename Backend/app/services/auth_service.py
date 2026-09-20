from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.db.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_token(
    subject: UUID, token_type: str, expires_delta: timedelta, token_id: str | None = None
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if token_id is not None:
        payload["jti"] = token_id
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User) -> str:
    return create_token(
        user.id,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user: User, token_id: str | None = None) -> str:
    return create_token(
        user.id,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
        token_id,
    )


def decode_token_claims(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != expected_type:
            raise ValueError("Invalid token type")
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Token subject is missing")
        return payload
    except (JWTError, ValueError, TypeError) as exc:
        raise ValueError("Invalid or expired token") from exc


def decode_token(token: str, expected_type: str) -> UUID:
    return UUID(decode_token_claims(token, expected_type)["sub"])