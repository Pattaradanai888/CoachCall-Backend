# scr/auth/service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from starlette.responses import JSONResponse

from src.auth.models import User
from src.auth.schemas import Token, UserCreate
from src.database import AsyncSessionLocal
from src.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    verify_password
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def register_user(user: UserCreate, db: AsyncSession):
    hashed = pwd_context.hash(user.password)
    db_user = User(email=user.email, fullname=user.fullname, password=hashed)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def authenticate_user(email: str, password: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return user

def generate_tokens(sub: str) -> Token:
    return Token(
        access_token=create_access_token({"sub": sub}),
        refresh_token=create_refresh_token({"sub": sub}),
        token_type="bearer"
    )

async def login_user_and_set_cookie(
    form_data: OAuth2PasswordRequestForm,
    db: AsyncSession,
    response: Response
) -> dict:
    user = await authenticate_user(form_data.username, form_data.password, db)
    token_data = generate_tokens(user.email)

    response.set_cookie(
        key="refresh_token",
        value=token_data.refresh_token,
        httponly=True,
        secure=False,  # Set to True in production
        samesite="strict",
        path="/",  # Ensures cookie is sent to /auth/* endpoints
        max_age=60 * 60 * 24 * 7  # 7 days
    )

    return {
        "access_token": token_data.access_token,
        "token_type": "bearer"
    }

async def refresh_access_token_service(refresh_token: str) -> dict:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_access_token(refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return {
        "access_token": create_access_token({"sub": payload["sub"]}),
        "token_type": "bearer"
    }

async def logout_user(db: AsyncSession) -> JSONResponse:
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=False,  # Set to True in production
        samesite="strict",
        path="/"  # Matches the path set in login
    )
    return response