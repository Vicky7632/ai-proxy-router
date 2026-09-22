import hashlib
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.api_key import APIKey
from app.db.session import get_db


def get_api_key(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> APIKey:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    raw_key = authorization.removeprefix("Bearer ").strip()
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key = (
        db.query(APIKey)
        .filter(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None),
            APIKey.is_active.is_(True),
        )
        .first()
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )
    return api_key
