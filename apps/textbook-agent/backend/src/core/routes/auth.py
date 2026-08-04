import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from core.rate_limit import limiter
from pydantic import BaseModel

from core.auth.google_auth import verify_google_token
from core.auth.jwt_handler import JWTHandler
from core.dependencies import get_jwt_handler, get_settings, get_user_repository
from core.entities.user import User
from core.ports.user_repository import UserRepository
from core.auth.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class GoogleAuthRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


@router.post("/google", response_model=AuthResponse)
@limiter.limit("20/minute")
async def google_login(
    request: Request,
    body: GoogleAuthRequest,
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    user_repo: UserRepository = Depends(get_user_repository),
):
    try:
        google_user = await asyncio.to_thread(
            verify_google_token, body.credential, get_settings().google_client_id
        )
    except ValueError as exc:
        logger.warning("Google token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        )

    user = await user_repo.find_by_email(google_user.email)

    if user is None:
        now = datetime.now(timezone.utc)
        user = await user_repo.create(
            User(
                id=str(uuid.uuid4()),
                email=google_user.email,
                name=google_user.name,
                picture_url=google_user.picture_url,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        if user.name != google_user.name or user.picture_url != google_user.picture_url:
            user.name = google_user.name
            user.picture_url = google_user.picture_url
            user = await user_repo.update(user)

    access_token = jwt_handler.create_access_token(user.id, user.email)
    return AuthResponse(access_token=access_token, user=user)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
