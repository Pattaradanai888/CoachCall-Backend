# tests/unit/profile/test_schemas.py
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError, EmailStr

from src.auth.models import User, UserProfile
from src.profile.schemas import ProfileUpdate, PasswordUpdate, ProfileResponse


# --- Test ID: UTC-36 ---
class TestProfileSchemas:
    """Tests for Pydantic schema validation and serialization for the profile module."""

    def test_profile_update_valid_partial_data(self):
        """UTC-36-TC-01: Success: ProfileUpdate with valid partial data."""
        data = ProfileUpdate(fullname="New Full Name")
        assert data.fullname == "New Full Name"
        assert data.email is None

    def test_profile_update_invalid_email(self):
        """UTC-36-TC-02: Failure: ProfileUpdate with invalid email."""
        with pytest.raises(ValidationError):
            ProfileUpdate(email="not-a-valid-email")

    def test_password_update_short_password(self):
        """UTC-36-TC-03: Failure: PasswordUpdate with a new password that is too short."""
        with pytest.raises(ValidationError) as exc_info:
            PasswordUpdate(
                current_password="old_password123",
                new_password="short",
                confirm_password="short"
            )
        # Check that the error message is for the new_password field
        assert "new_password" in str(exc_info.value)
        assert "at least 8 characters" in str(exc_info.value)

    def test_profile_response_serialization(self):
        """UTC-36-TC-04: Success: ProfileResponse serialization from a dictionary."""
        user_data = {
            "id": 123,
            "email": "test@example.com",
            "fullname": "Test User Fullname",
            "profile_image_url": "http://example.com/profile.png"
        }

        # Create the Pydantic model from a dictionary
        response = ProfileResponse(**user_data)

        # Assert the fields were populated correctly
        assert response.id == 123
        assert response.email == "test@example.com"
        assert response.fullname == "Test User Fullname"
        assert response.profile_image_url == "http://example.com/profile.png"