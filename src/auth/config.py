# src/auth/config.py
from pydantic import field_validator
from pydantic_settings import BaseSettings,SettingsConfigDict

class AuthSettings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int

    @field_validator('JWT_SECRET')
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError('JWT_SECRET must be at least 32 characters long')
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

auth_settings = AuthSettings()