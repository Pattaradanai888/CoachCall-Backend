# src/auth/schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    fullname: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserRead(BaseModel):
    id: int
    email: EmailStr
    fullname: str

    model_config = ConfigDict(from_attributes=True)