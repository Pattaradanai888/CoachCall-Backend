# src/auth/dependencies.py
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.exceptions import CredentialsException
from src.auth.models import User, BlacklistedToken
from src.auth.utils import decode_access_token
from src.database import get_async_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)):
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not username or not jti:
            raise CredentialsException
    except Exception:
        raise CredentialsException

    # Check if token is blacklisted using asynchronous select
    blacklist_query = await db.execute(
        select(BlacklistedToken).where(BlacklistedToken.jti == jti)
    )
    blacklisted_token = blacklist_query.scalars().first()
    if blacklisted_token:
        raise CredentialsException  # Token is blacklisted

    # Fetch user using asynchronous select
    user_query = await db.execute(
        select(User).where(User.username == username)
    )
    user = user_query.scalars().first()
    if user is None:
        raise CredentialsException

    return {"username": username, "id": user.id}
