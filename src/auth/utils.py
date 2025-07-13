# src/auth/utils.py
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from src.auth.config import auth_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM
    )


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=auth_settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM
    )


def decode_access_token(token: str):
    """
    Decodes a JWT token, raising specific HTTPExceptions for common errors.
    """
    try:
        payload = jwt.decode(
            token, auth_settings.JWT_SECRET, algorithms=[auth_settings.JWT_ALGORITHM]
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        ) from None
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate token: {e}",
        ) from None
