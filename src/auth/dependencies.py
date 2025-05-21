# src/auth/dependencies.py
from fastapi import Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.auth.exceptions import CredentialsException
from src.auth.models import User, BlacklistedToken
from src.auth.utils import decode_access_token
from src.database import get_async_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    request: Request, # Inject the Request object
    db: AsyncSession = Depends(get_async_session)
) -> User:
    token = request.cookies.get("access_token") # Get token from cookie

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}, # Standard practice
    )

    if not token:
        # Fallback: check Authorization header (optional, if you want to support both)
        # auth_header = request.headers.get("Authorization")
        # if auth_header:
        #     parts = auth_header.split()
        #     if len(parts) == 2 and parts[0].lower() == "bearer":
        #         token = parts[1]
        # if not token: # If still no token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (no token found in cookies)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token) # Use your existing utility
        email: str = payload.get("sub")
        jti: str = payload.get("jti") # Get jti for blacklisting

        if email is None:
            raise credentials_exception
        if jti is None: # jti is crucial for logout
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing jti for blacklist check",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except HTTPException as e: # If decode_access_token raises HTTPException
        raise e
    except PyJWTError: # Catch any other JWT errors if decode_access_token doesn't raise HTTPException
        raise credentials_exception

    # Check if token is blacklisted
    blacklisted_token_entry = await db.execute(
        select(BlacklistedToken).where(BlacklistedToken.jti == jti)
    )
    if blacklisted_token_entry.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been blacklisted (logged out)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalars().first()
    if user is None:
        raise credentials_exception
    return user
