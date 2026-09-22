import hashlib
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models.api_key import APIKey
from app.db.session import get_db

api_key_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def get_api_key(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(api_key_scheme),
    ] = None,
) -> APIKey:
    if credentials is not None:
        logger.info("API key auth scheme received: %s", credentials.scheme)
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    raw_key = credentials.credentials.strip()
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
    logger.info(
        "API key lookup hash=%s match=%s database=%s host=%s",
        key_hash,
        api_key is not None,
        db.bind.url.database if db.bind is not None else None,
        db.bind.url.host if db.bind is not None else None,
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )
    return api_key
