# src/password_reset/schemas.py
from pydantic import BaseModel, EmailStr, Field


class RequestResetSchema(BaseModel):
    email: EmailStr


class VerifyOTPSchema(BaseModel):
    email: EmailStr
    otp: str = Field(
        ..., min_length=6, max_length=6, description="The 6-digit code from the email."
    )


class ResetPasswordSchema(BaseModel):
    email: EmailStr
    otp: str = Field(
        ..., min_length=6, max_length=6, description="The 6-digit code from the email."
    )
    new_password: str = Field(
        ..., min_length=8, description="The new password for the account."
    )
