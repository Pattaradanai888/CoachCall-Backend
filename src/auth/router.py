# src/auth/router.py
import os

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, get_optional_current_user
from src.auth.models import User
from src.auth.schemas import Token, UserCreate, UserRead
from src.auth.service import login_user, logout_user, refresh_tokens, register_user
from src.database import get_async_session

router = APIRouter()

IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"

COOKIE_SETTINGS = {
    "key": "refresh_token",
    "path": "/",
    "httponly": True,
    "secure": True,
}


@router.post("/token", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session),
):
    token = await login_user(form_data.username, form_data.password, db)

    # Set refresh token cookie with consistent settings
    response.set_cookie(
        value=token.refresh_token,
        max_age=7 * 24 * 3600,  # 7 days in seconds
        **COOKIE_SETTINGS,
    )

    return token


@router.post("/refresh", response_model=Token)
async def refresh(request: Request, response: Response):
    old_refresh = request.cookies.get(COOKIE_SETTINGS["key"])

    # Rotate tokens
    token = await refresh_tokens(old_refresh)

    # Set a new refresh token cookie with SAME settings
    response.set_cookie(
        value=token.refresh_token,
        max_age=7 * 24 * 3600,  # 7 days in seconds
        **COOKIE_SETTINGS,
    )

    return token


@router.post("/logout")
async def logout(response: Response):
    await logout_user()

    # Delete cookie with SAME settings (except value/max_age)
    response.delete_cookie(**COOKIE_SETTINGS)

    return {"message": "Logged out successfully"}


@router.post("/register", response_model=UserRead)
async def register(user: UserCreate, db: AsyncSession = Depends(get_async_session)):
    return await register_user(user, db)


@router.get("/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.get("/verify")
async def verify_token(
    current_user: User | None = Depends(get_optional_current_user),
):
    return {
        "valid": current_user is not None,
        "user_id": current_user.id if current_user else None,
    }
