# src/auth/config.py
from pydantic_settings import BaseSettings

class AuthSettings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = {
        "env_file": ".env",
        "extra": "ignore"  # This will ignore extra fields
    }

auth_settings = AuthSettings()