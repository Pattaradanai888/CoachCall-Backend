# src/auth/router.py
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.schemas import UserCreate, Token
from src.auth.service import register_user, login_for_access_token, get_db, blacklist_token
from src.auth.dependencies import get_current_user, oauth2_scheme
from src.database import get_async_session

router = APIRouter()

@router.post("/register", response_model=UserCreate)
async def register(user: UserCreate, db: AsyncSession = Depends(get_async_session)):
    return await register_user(user, db)

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_session)):
    return await login_for_access_token(form_data, db)

@router.get("/me")
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)):
    return await blacklist_token(token, db)
