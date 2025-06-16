# src/auth/schemas.py
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field


class UserCreate(BaseModel):
    fullname: str
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class UserProfileRead(BaseModel):
    display_name: str
    profile_image_url: Optional[str] = None

class UserRead(BaseModel):
    id: int
    email: str
    profile: Optional[UserProfileRead] = None

    model_config = ConfigDict(from_attributes=True)