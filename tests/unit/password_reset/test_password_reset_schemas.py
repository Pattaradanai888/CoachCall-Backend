# tests/unit/password_reset/test_schemas.py

import pytest
from pydantic import ValidationError

from src.password_reset.schemas import RequestResetSchema, VerifyOTPSchema, ResetPasswordSchema


# --- Test ID: UTC-37 ---
class TestPasswordResetSchemas:
    """Tests for Pydantic schema validation for the password_reset module."""

    # --- Tests for RequestResetSchema ---

    def test_request_reset_valid_email(self):
        """UTC-37-TC-01: Success: RequestResetSchema with a valid email."""
        data = RequestResetSchema(email="test@example.com")
        assert data.email == "test@example.com"

    def test_request_reset_invalid_email(self):
        """UTC-37-TC-02: Failure: RequestResetSchema with an invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            RequestResetSchema(email="not-a-valid-email")
        # Check that the error message is related to the email field
        assert "email" in str(exc_info.value)

    # --- Tests for VerifyOTPSchema ---

    def test_verify_otp_valid_data(self):
        """UTC-37-TC-03: Success: VerifyOTPSchema with valid email and OTP."""
        data = VerifyOTPSchema(email="test@example.com", otp="123456")
        assert data.email == "test@example.com"
        assert data.otp == "123456"

    def test_verify_otp_too_short(self):
        """UTC-37-TC-04: Failure: VerifyOTPSchema with an OTP that is too short."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyOTPSchema(email="test@example.com", otp="12345")
        # Check that the error is for the 'otp' field and mentions the length
        assert "otp" in str(exc_info.value)
        assert "6 characters" in str(exc_info.value)

    def test_verify_otp_too_long(self):
        """UTC-37-TC-05: Failure: VerifyOTPSchema with an OTP that is too long."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyOTPSchema(email="test@example.com", otp="1234567")
        # Check that the error is for the 'otp' field and mentions the length
        assert "otp" in str(exc_info.value)
        assert "6 characters" in str(exc_info.value)

    # --- Tests for ResetPasswordSchema ---

    def test_reset_password_valid_data(self):
        """UTC-37-TC-06: Success: ResetPasswordSchema with all valid data."""
        data = ResetPasswordSchema(
            email="test@example.com",
            otp="654321",
            new_password="a_very_secure_password_123"
        )
        assert data.email == "test@example.com"
        assert data.otp == "654321"
        assert data.new_password == "a_very_secure_password_123"

    def test_reset_password_new_password_too_short(self):
        """UTC-37-TC-07: Failure: ResetPasswordSchema with a new password that is too short."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordSchema(
                email="test@example.com",
                otp="654321",
                new_password="short"
            )
        # Check that the error is specifically for the new_password field
        assert "new_password" in str(exc_info.value)
        assert "at least 8 characters" in str(exc_info.value)

    def test_reset_password_missing_field(self):
        """UTC-37-TC-08: Failure: ResetPasswordSchema with a missing required field."""
        with pytest.raises(ValidationError) as exc_info:
            # Missing the 'otp' field
            ResetPasswordSchema(
                email="test@example.com",
                new_password="valid_password_again"
            )
        # Check that the error message indicates a missing field
        assert "otp" in str(exc_info.value)
        assert "Field required" in str(exc_info.value)