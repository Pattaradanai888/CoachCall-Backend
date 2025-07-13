# src/upload/schemas.py
from enum import Enum

from pydantic import BaseModel


class ImageType(str, Enum):
    PROFILE = "profile"
    ATHLETE = "athlete"
    COURSE = "course"


class ImageConfig(BaseModel):
    max_width: int = 1200
    max_height: int = 1200
    quality: int = 85
    allowed_extensions: list[str] = [".jpg", ".jpeg", ".png", ".webp"]
    max_file_size: int = 5 * 1024 * 1024


class UploadResult(BaseModel):
    url: str
    blob_name: str
    file_size: int


class UploadResponse(BaseModel):
    url: str
