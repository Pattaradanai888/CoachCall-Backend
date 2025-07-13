# src/profile/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureSettings(BaseSettings):
    AZURE_STORAGE_ACCOUNT: str
    AZURE_STORAGE_KEY: str
    AZURE_CONTAINER_NAME: str = "profile-images"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


azure_settings = AzureSettings()
