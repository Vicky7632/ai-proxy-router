from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.services.auth_service import decode_token_claims
from app.services.redis_service import is_token_blacklisted


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication cookie required",
        )

    try:
        claims = decode_token_claims(access_token, "access")
        token_id = claims.get("jti")
        if not token_id or is_token_blacklisted(token_id):
            raise ValueError("Access token has been revoked")
        user_id = UUID(claims["sub"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
