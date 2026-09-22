import hashlib
import secrets

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.models.api_key import APIKey
from app.db.models.user import User
from app.db.session import get_db
from app.middleware.auth import get_current_user

router = APIRouter(tags=["keys"])


@router.post("/keys", status_code=status.HTTP_201_CREATED)
def create_api_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    raw_key = f"sk-{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    api_key = APIKey(user_id=current_user.id, key_hash=key_hash, name="default")
    db.add(api_key)
    db.commit()

    return {"api_key": raw_key}