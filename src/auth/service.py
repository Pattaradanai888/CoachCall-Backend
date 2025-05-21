# src/auth/service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from src.auth.models import User, BlacklistedToken
from src.auth.schemas import Token, UserCreate
from src.database import AsyncSessionLocal, get_async_session
from src.auth.utils import create_access_token, verify_password, decode_access_token

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
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalars().first()

    if not user or not pwd_context.verify(password, user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return user

async def login_for_access_token(form_data: OAuth2PasswordRequestForm, db: AsyncSession) -> Token:
    user = await authenticate_user(form_data.username, form_data.password, db)
    access_token = create_access_token({"sub": user.email})
    return Token(access_token=access_token)


async def blacklist_token(token: str, db: AsyncSession):
    try:
        # Decode the token to extract the jti (unique token identifier)
        payload = decode_access_token(token)
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(status_code=400, detail="Invalid token: missing jti")

        existing = await db.execute(
            select(BlacklistedToken).where(BlacklistedToken.jti == jti)
        )
        if existing.scalars().first():
            return {"msg": "Token already blacklisted"}

        # Add the token to the blacklist
        blacklisted_token = BlacklistedToken(jti=jti)
        db.add(blacklisted_token)
        await db.commit()
        return {"msg": "Token blacklisted successfully"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")