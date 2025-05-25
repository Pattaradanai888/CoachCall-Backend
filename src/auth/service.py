# src/auth/service.py
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from src.auth.models import User
from src.auth.schemas import Token, UserCreate, UserRead
from src.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    verify_password,
    hash_password
)


async def register_user(user: UserCreate, db: AsyncSession):
    hashed = hash_password(user.password)
    db_user = User(email=user.email, fullname=user.fullname, password=hashed)
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return db_user


async def login_user(email: str, password: str, db: AsyncSession) -> Token:
    # Authenticate and generate tokens; no HTTP concerns here
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    access = create_access_token({"sub": user.email})
    refresh = create_refresh_token({"sub": user.email})
    return Token(access_token=access, refresh_token=refresh, token_type="bearer")


async def refresh_tokens(old_refresh: str) -> Token:
    if not old_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    try:
        payload = decode_access_token(old_refresh)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Rotate both tokens
    access = create_access_token({"sub": payload["sub"]})
    refresh = create_refresh_token({"sub": payload["sub"]})
    return Token(access_token=access, refresh_token=refresh, token_type="bearer")


async def logout_user() -> None:
    return
