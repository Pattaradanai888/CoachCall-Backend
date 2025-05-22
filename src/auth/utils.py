# src/auth/utils.py
import jwt
from datetime import datetime, timedelta

from fastapi import HTTPException
from jwt import PyJWTError

from src.auth.config import auth_settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=auth_settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, auth_settings.JWT_SECRET, algorithms=[auth_settings.JWT_ALGORITHM])
        return payload
    except PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Could not validate token: {str(e)}")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)