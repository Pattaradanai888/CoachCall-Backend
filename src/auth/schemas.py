# src/auth/schemas.py


from pydantic import BaseModel, ConfigDict, EmailStr

from src.auth.config import auth_settings


class UserCreate(BaseModel):
    fullname: str
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = auth_settings.TOKEN_TYPE


class UserProfileRead(BaseModel):
    display_name: str
    profile_image_url: str | None = None
    has_completed_onboarding: bool

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: int
    email: str
    profile: UserProfileRead | None = None

    model_config = ConfigDict(from_attributes=True)
