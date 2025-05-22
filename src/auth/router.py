# src/auth/router.py
from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.auth.schemas import UserCreate, Token, UserRead
from src.auth.service import (
    register_user,
    login_user_and_set_cookie,
    refresh_access_token_service,
    logout_user
)
from src.auth.dependencies import get_current_user
from src.database import get_async_session

router = APIRouter()

@router.post("/register", response_model=UserRead)
async def register(user: UserCreate, db: AsyncSession = Depends(get_async_session)) -> UserRead:
    return await register_user(user, db)

@router.post("/token", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    return await login_user_and_set_cookie(form_data, db, response)

@router.post("/refresh", response_model=Token)
async def refresh_access_token(request: Request):
    refresh_token = request.cookies.get("refresh_token")
    return await refresh_access_token_service(refresh_token)

@router.get("/me")
async def read_users_me(current_user=Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    return await logout_user(db)
