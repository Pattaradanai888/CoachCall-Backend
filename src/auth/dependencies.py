# src/auth/dependencies.py
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from src.auth.models import User
from src.auth.utils import decode_access_token
from src.database import get_async_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_session)
) -> User:
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token: Missing email/subject")
    except HTTPException as http_exc: # Use a distinct variable name
        raise http_exc
    except Exception as generic_exc:  # Use a distinct variable name
        # Use the exception variable from *this* block
        raise HTTPException(status_code=500, detail=f"Internal server error processing token: {str(generic_exc)}")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_optional_current_user(
        token: Optional[str] = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_async_session)
) -> Optional[User]:
    if not token:
        return None

    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None