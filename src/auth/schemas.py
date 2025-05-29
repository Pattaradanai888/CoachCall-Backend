# src/auth/schemas.py
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    fullname: str
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    email: str
    fullname: str
    profile_image_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
