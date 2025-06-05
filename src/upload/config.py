from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadSettings(BaseSettings):
    AZURE_STORAGE_ACCOUNT: str
    AZURE_STORAGE_KEY: str

    # Container names
    PROFILE_IMAGES_CONTAINER: str = "profile-images"
    DOCUMENT_CONTAINER: str = "documents"

    # Common settings
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
    IMAGE_QUALITY: int = 85

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


upload_settings = UploadSettings()