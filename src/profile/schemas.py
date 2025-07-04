# src/profile/schemas.py
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ProfileUpdate(BaseModel):
    fullname: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None


class PasswordUpdate(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class ProfileResponse(BaseModel):
    id: int
    email: str
    fullname: str
    profile_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)