# src/auth/router.py
from typing import Any, Coroutine

from fastapi import APIRouter, Depends, Response, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.auth.models import User
from src.auth.schemas import UserCreate, Token, UserRead
from src.auth.service import register_user, login_user, refresh_tokens, logout_user as service_logout, logout_user
from src.auth.dependencies import get_current_user
from src.database import get_async_session

router = APIRouter()

COOKIE_SETTINGS = {
    "key": "refresh_token",
    "path": "/",
    "httponly": True,
    "secure": False,  # Set to True in deployment
    "samesite": "lax"
}


@router.post("/token", response_model=Token)
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_async_session)):
    token = await login_user(form_data.username, form_data.password, db)

    # Set refresh token cookie with consistent settings
    response.set_cookie(
        value=token.refresh_token,
        max_age=7 * 24 * 3600,  # 7 days in seconds
        **COOKIE_SETTINGS
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
        **COOKIE_SETTINGS
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
