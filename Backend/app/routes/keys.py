import hashlib
import secrets
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.api_key import APIKey
from app.db.models.user import User
from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.schemas.api_key import APIKeyCreate, APIKeyCreateResponse, APIKeyResponse

router = APIRouter(tags=["keys"])


@router.post("/keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    request: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> APIKeyCreateResponse:
    raw_key = f"sk-{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    api_key = APIKey(user_id=current_user.id, key_hash=key_hash, name=request.name)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        created_at=api_key.created_at,
        revoked_at=api_key.revoked_at,
        api_key=raw_key,
    )


@router.get("/keys", response_model=list[APIKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[APIKey]:
    return (
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id)
        .order_by(APIKey.created_at.desc())
        .all()
    )


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    api_key = (
        db.query(APIKey)
        .filter(APIKey.id == key_id, APIKey.user_id == current_user.id)
        .first()
    )
    if api_key is None or api_key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.revoked_at = datetime.utcnow()
    api_key.is_active = False
    db.commit()
