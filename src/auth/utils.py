# src/auth/utils.py
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError

from src.auth.config import auth_settings


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)


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
