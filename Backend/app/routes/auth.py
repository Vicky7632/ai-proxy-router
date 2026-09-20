from datetime import timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_claims,
    hash_password,
    verify_password,
)
from app.services.redis_service import (
    consume_refresh_token,
    revoke_refresh_token,
    store_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for_user(user: User) -> TokenResponse:
    refresh_token_id = str(uuid4())
    refresh_token = create_refresh_token(user, refresh_token_id)
    try:
        store_refresh_token(
            refresh_token_id,
            str(user.id),
            int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: UserCreate, db: Annotated[Session, Depends(get_db)]
) -> User:
    email = request.email.lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(email=email, hashed_password=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _tokens_for_user(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: RefreshTokenRequest, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    try:
        claims = decode_token_claims(request.refresh_token, "refresh")
        user_id = decode_token(request.refresh_token, "refresh")
        token_id = claims.get("jti")
        if not token_id or not consume_refresh_token(token_id, str(user_id)):
            raise ValueError("Refresh token has been revoked or already used")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    new_tokens = _tokens_for_user(user)
    return new_tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: RefreshTokenRequest) -> None:
    try:
        claims = decode_token_claims(request.refresh_token, "refresh")
        token_id = claims.get("jti")
        if token_id:
            revoke_refresh_token(token_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError:
        return


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user