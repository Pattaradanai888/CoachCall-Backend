# src/profile/schemas.py

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileUpdate(BaseModel):
    fullname: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None


class PasswordUpdate(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class ProfileResponse(BaseModel):
    id: int
    email: str
    fullname: str
    profile_image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
