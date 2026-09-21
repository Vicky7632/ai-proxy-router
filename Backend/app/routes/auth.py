from datetime import timedelta
from time import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.schemas.auth import LoginRequest, MessageResponse, UserCreate, UserResponse
from app.services.auth_service import (
    create_access_token, create_refresh_token, decode_token, decode_token_claims,
    hash_password, verify_password,
)
from app.services.redis_service import (
    blacklist_token, consume_refresh_token, is_token_blacklisted,
    revoke_refresh_token, store_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, user: User) -> None:
    access_token = create_access_token(user)
    refresh_token_id = str(uuid4())
    refresh_token = create_refresh_token(user, refresh_token_id)
    try:
        store_refresh_token(
            refresh_token_id, str(user.id),
            int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response.set_cookie("access_token", access_token,
                        max_age=settings.access_token_expire_minutes * 60,
                        httponly=True, secure=settings.cookie_secure,
                        samesite=settings.cookie_samesite, path="/")
    response.set_cookie("refresh_token", refresh_token,
                        max_age=settings.refresh_token_expire_days * 86400,
                        httponly=True, secure=settings.cookie_secure,
                        samesite=settings.cookie_samesite, path="/auth")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: UserCreate, db: Annotated[Session, Depends(get_db)]) -> User:
    email = request.email.lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    user = User(first_name=request.first_name, last_name=request.last_name,
                email=email, hashed_password=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=MessageResponse)
def login(request: LoginRequest, response: Response,
          db: Annotated[Session, Depends(get_db)]) -> MessageResponse:
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _set_auth_cookies(response, user)
    return MessageResponse(message="Login successful")


@router.post("/refresh", response_model=MessageResponse)
def refresh(response: Response, db: Annotated[Session, Depends(get_db)],
            refresh_token: Annotated[str | None, Cookie()] = None) -> MessageResponse:
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Refresh token cookie required")
    try:
        claims = decode_token_claims(refresh_token, "refresh")
        user_id = decode_token(refresh_token, "refresh")
        token_id = claims.get("jti")
        if (not token_id or is_token_blacklisted(token_id)
                or not consume_refresh_token(token_id, str(user_id))):
            raise ValueError("Refresh token has been revoked or already used")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    _set_auth_cookies(response, user)
    return MessageResponse(message="Token refreshed")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, current_user: Annotated[User, Depends(get_current_user)],
           access_token: Annotated[str | None, Cookie()] = None,
           refresh_token: Annotated[str | None, Cookie()] = None) -> None:
    if access_token is None or refresh_token is None:
        raise HTTPException(status_code=401, detail="Authentication cookies required")
    try:
        access_claims = decode_token_claims(access_token, "access")
        refresh_claims = decode_token_claims(refresh_token, "refresh")
        access_token_id = access_claims.get("jti")
        refresh_token_id = refresh_claims.get("jti")
        if (not access_token_id or not refresh_token_id
                or refresh_claims.get("sub") != str(current_user.id)):
            raise ValueError("Refresh token does not belong to the current user")
        blacklist_token(access_token_id, int(access_claims["exp"]) - int(time()))
        revoke_refresh_token(refresh_token_id, int(refresh_claims["exp"]) - int(time()))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/auth")


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
