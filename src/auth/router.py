# src/auth/router.py
from fastapi import APIRouter, Depends, Response, HTTPException, status , Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.schemas import UserCreate, Token, UserRead
from src.auth.service import register_user, login_for_access_token, get_db, blacklist_token
from src.auth.dependencies import get_current_user, oauth2_scheme
from src.database import get_async_session

router = APIRouter()

@router.post("/register", response_model=UserRead)
async def register(user: UserCreate,db: AsyncSession = Depends(get_async_session)) -> UserRead:
    return await register_user(user, db)

@router.post("/token", response_model=Token)
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_session)):
    token_data = await login_for_access_token(form_data, db)
    response.set_cookie(
        key="access_token",
        value=token_data.access_token,
        httponly=True,
        secure=False,       # set True in production (HTTPS)
        samesite="strict",
        max_age=30 * 60,    # 30 min session
        path="/",
    )
    return token_data

@router.get("/me")
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (no token cookie found for logout)"
        )
    result = await blacklist_token(token, db)
    response = JSONResponse(content=result)
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=False, # Should be True in production (HTTPS)
        samesite="strict",
        path="/"
    )
    return response