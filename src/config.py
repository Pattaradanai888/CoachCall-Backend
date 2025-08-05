# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    CORS_ORIGINS: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


class EmailSettings(BaseSettings):
    COMMUNICATION_SERVICES_CONNECTION_STRING: str
    SENDER_ADDRESS: str
    OTP_EXPIRE_MINUTES: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


email_settings = EmailSettings()
