# src/auth/service.py
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.config import auth_settings
from src.auth.models import User, UserProfile
from src.auth.schemas import Token, UserCreate
from src.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)


async def register_user(user: UserCreate, db: AsyncSession):
    hashed_password = hash_password(user.password)
    db_user = User(
        email=user.email,
        password=hashed_password,
        profile=UserProfile(display_name=user.fullname),
    )
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)

        stmt = (
            select(User)
            .options(selectinload(User.profile))
            .where(User.id == db_user.id)
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration.",
        ) from None


async def login_user(email: str, password: str, db: AsyncSession) -> Token:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access = create_access_token({"sub": user.email})
    refresh = create_refresh_token({"sub": user.email})
    return Token(
        access_token=access, refresh_token=refresh, token_type=auth_settings.TOKEN_TYPE
    )


async def refresh_tokens(old_refresh: str) -> Token:
    if not old_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided"
        )

    payload = decode_access_token(old_refresh)

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Subject claim missing",
        )

    access = create_access_token({"sub": email})
    refresh = create_refresh_token({"sub": email})
    return Token(
        access_token=access, refresh_token=refresh, token_type=auth_settings.TOKEN_TYPE
    )


async def logout_user() -> None:
    return

# The 'mark_onboarding_as_complete' function has been removed from this file.