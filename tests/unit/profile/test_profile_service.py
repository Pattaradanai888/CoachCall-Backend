# tests/unit/profile/test_service.py
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.auth.models import User, UserProfile
from src.profile.schemas import ProfileUpdate, PasswordUpdate
from src.profile.service import (
    update_profile, change_password, upload_profile_image, delete_profile_image, mark_onboarding_as_complete
)
from src.upload.schemas import UploadResponse, ImageType


@pytest.fixture
def mock_db_session():
    """Provides a mocked async database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_user_with_profile():
    """Provides a reusable mock User with a nested mock UserProfile."""
    mock_profile = MagicMock(spec=UserProfile)
    mock_profile.display_name = "Old Name"
    mock_profile.profile_image_url = None

    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "old@example.com"
    mock_user.password = "hashed_old_password"
    mock_user.profile = mock_profile
    return mock_user


# --- Test ID: UTC-37 ---
@pytest.mark.asyncio
class TestUpdateProfileService:
    async def test_update_fullname_success(self, mock_user_with_profile, mock_db_session):
        """UTC-37-TC-01: Success: Update only the fullname."""
        profile_data = ProfileUpdate(fullname="New Full Name")

        updated_user = await update_profile(mock_user_with_profile, profile_data, mock_db_session)

        assert updated_user.profile.display_name == "New Full Name"
        assert updated_user.email == "old@example.com"  # Email should not change
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once_with(updated_user)

    async def test_update_email_success(self, mock_user_with_profile, mock_db_session):
        """UTC-37-TC-02: Success: Update the email to a new, unused address."""
        # Mock db.execute to find no existing user with the new email
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        profile_data = ProfileUpdate(email="new@example.com")
        updated_user = await update_profile(mock_user_with_profile, profile_data, mock_db_session)

        assert updated_user.email == "new@example.com"
        mock_db_session.commit.assert_awaited_once()

    async def test_update_email_conflict_failure(self, mock_user_with_profile, mock_db_session):
        """UTC-37-TC-03: Failure: Attempt to update email to an address that is already registered."""
        # Mock db.execute to find an existing user
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = User(id=2, email="new@example.com")
        mock_db_session.execute.return_value = mock_result

        profile_data = ProfileUpdate(email="new@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await update_profile(mock_user_with_profile, profile_data, mock_db_session)

        assert exc_info.value.status_code == 409
        assert "Email already registered" in exc_info.value.detail
        mock_db_session.rollback.assert_awaited_once()

    async def test_update_no_profile_failure(self, mock_user_with_profile, mock_db_session):
        """UTC-37-TC-04: Failure: The user object lacks a profile (internal error state)."""
        mock_user_with_profile.profile = None  # Simulate missing profile
        profile_data = ProfileUpdate(fullname="Any Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_profile(mock_user_with_profile, profile_data, mock_db_session)

        assert exc_info.value.status_code == 500
        assert "User profile not found" in exc_info.value.detail


# --- Test ID: UTC-38 ---
@pytest.mark.asyncio
@patch("src.profile.service.hash_password")
@patch("src.profile.service.verify_password")
class TestChangePasswordService:
    async def test_change_password_success(self, mock_verify, mock_hash, mock_user_with_profile, mock_db_session):
        """UTC-38-TC-01: Success: Change password with valid data."""
        mock_verify.side_effect = [True, False]  # Current pass is correct, new pass is not same as old
        mock_hash.return_value = "hashed_new_password"
        password_data = PasswordUpdate(
            current_password="old_password",
            new_password="new_password_123",
            confirm_password="new_password_123"
        )
        await change_password(mock_user_with_profile, password_data, mock_db_session)

        assert mock_user_with_profile.password == "hashed_new_password"
        mock_db_session.commit.assert_awaited_once()

    async def test_change_password_incorrect_current_failure(self, mock_verify, mock_hash, mock_user_with_profile, mock_db_session):
        """UTC-38-TC-02: Failure: The provided current_password is incorrect."""
        mock_verify.return_value = False
        password_data = PasswordUpdate(
            current_password="incorrect_password",
            new_password="a_valid_new_password",
            confirm_password="a_valid_new_password"
        )

        with pytest.raises(HTTPException) as exc_info:
            await change_password(mock_user_with_profile, password_data, mock_db_session)
        assert exc_info.value.status_code == 400
        assert "Current password is incorrect" in exc_info.value.detail

    async def test_change_password_mismatch_failure(self, mock_verify, mock_hash, mock_user_with_profile, mock_db_session):
        """UTC-38-TC-03: Failure: The new_password and confirm_password do not match."""
        mock_verify.return_value = True
        password_data = PasswordUpdate(
            current_password="any", new_password="new_password", confirm_password="does_not_match"
        )
        with pytest.raises(HTTPException) as exc_info:
            await change_password(mock_user_with_profile, password_data, mock_db_session)
        assert exc_info.value.status_code == 400
        assert "New password and confirmation do not match" in exc_info.value.detail

    async def test_change_password_same_as_old_failure(self, mock_verify, mock_hash, mock_user_with_profile, mock_db_session):
        """UTC-38-TC-04: Failure: The new password is the same as the old password."""
        mock_verify.side_effect = [True, True] # Both current and new password checks return True
        password_data = PasswordUpdate(
            current_password="any", new_password="same_password", confirm_password="same_password"
        )
        with pytest.raises(HTTPException) as exc_info:
            await change_password(mock_user_with_profile, password_data, mock_db_session)
        assert exc_info.value.status_code == 400
        assert "New password must be different" in exc_info.value.detail


# --- Test ID: UTC-39 ---
@pytest.mark.asyncio
@patch("src.profile.service.image_upload_service", new_callable=AsyncMock)
class TestUploadProfileImageService:
    async def test_upload_first_time_success(self, mock_image_service, mock_user_with_profile, mock_db_session):
        """UTC-39-TC-01: Success: Upload an image for the first time."""
        mock_user_with_profile.profile.profile_image_url = None
        mock_image_service.upload_image.return_value = UploadResponse(url="http://new.url/img.png")

        new_url = await upload_profile_image(mock_user_with_profile, MagicMock(), mock_db_session)

        assert new_url == "http://new.url/img.png"
        mock_image_service.delete_image.assert_not_called()
        assert mock_user_with_profile.profile.profile_image_url == "http://new.url/img.png"
        mock_db_session.commit.assert_awaited_once()

    async def test_upload_replace_success(self, mock_image_service, mock_user_with_profile, mock_db_session):
        """UTC-39-TC-02: Success: Replace an existing profile image."""
        mock_user_with_profile.profile.profile_image_url = "http://old.url/img.png"
        mock_image_service.upload_image.return_value = UploadResponse(url="http://new.url/img.png")

        await upload_profile_image(mock_user_with_profile, MagicMock(), mock_db_session)

        mock_image_service.delete_image.assert_awaited_once_with("http://old.url/img.png")
        mock_image_service.upload_image.assert_awaited_once()
        assert mock_user_with_profile.profile.profile_image_url == "http://new.url/img.png"

    async def test_upload_service_failure(self, mock_image_service, mock_user_with_profile, mock_db_session):
        """UTC-39-TC-03: Failure: The external image upload service fails."""
        mock_image_service.upload_image.side_effect = Exception("Cloud service is down")

        with pytest.raises(HTTPException) as exc_info:
            await upload_profile_image(mock_user_with_profile, MagicMock(), mock_db_session)
        assert exc_info.value.status_code == 500
        mock_db_session.rollback.assert_awaited_once()


# --- Test ID: UTC-40 ---
@pytest.mark.asyncio
@patch("src.profile.service.image_upload_service", new_callable=AsyncMock)
class TestDeleteProfileImageService:
    async def test_delete_success(self, mock_image_service, mock_user_with_profile, mock_db_session):
        """UTC-40-TC-01: Success: Delete an existing profile image."""
        mock_user_with_profile.profile.profile_image_url = "http://todelete.url/img.png"
        await delete_profile_image(mock_user_with_profile, mock_db_session)

        mock_image_service.delete_image.assert_awaited_once_with("http://todelete.url/img.png")
        assert mock_user_with_profile.profile.profile_image_url is None
        mock_db_session.commit.assert_awaited_once()

    async def test_delete_no_image_failure(self, mock_image_service, mock_user_with_profile, mock_db_session):
        """UTC-40-TC-02: Failure: Attempt to delete an image when none exists."""
        mock_user_with_profile.profile.profile_image_url = None
        with pytest.raises(HTTPException) as exc_info:
            await delete_profile_image(mock_user_with_profile, mock_db_session)
        assert exc_info.value.status_code == 404
        assert "No profile image found" in exc_info.value.detail
        mock_image_service.delete_image.assert_not_called()

    async def test_delete_service_failure(self, mock_image_service, mock_user_with_profile, mock_db_session):
        """UTC-40-TC-03: Failure: The external image deletion service fails."""
        mock_user_with_profile.profile.profile_image_url = "http://todelete.url/img.png"
        mock_image_service.delete_image.side_effect = Exception("Cloud service error")

        with pytest.raises(HTTPException) as exc_info:
            await delete_profile_image(mock_user_with_profile, mock_db_session)
        assert exc_info.value.status_code == 500
        mock_db_session.rollback.assert_awaited_once()

# --- Test ID: UTC-50 ---
@pytest.mark.asyncio
class TestMarkOnboardingAsComplete:
    async def test_mark_onboarding_as_complete_success(self, mock_user_with_profile, mock_db_session):
        """UTC-50-TC-01: Success: Mark onboarding as complete for an existing user."""
        # Arrange: Ensure the initial state is 'not completed'
        mock_user_with_profile.profile.has_completed_onboarding = False

        # Mock the database query to find the user's profile
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user_with_profile.profile
        mock_db_session.execute.return_value = mock_result

        # Act
        updated_profile = await mark_onboarding_as_complete(
            user_id=mock_user_with_profile.id, db=mock_db_session
        )

        # Assert
        assert updated_profile.has_completed_onboarding is True
        # The session tracks changes on existing objects, so .add() is not called.
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once_with(updated_profile)

    async def test_mark_onboarding_profile_not_found_failure(self, mock_db_session):
        """UTC-50-TC-02: Failure: Attempt to mark onboarding for a non-existent user profile."""
        # Arrange: Mock the database query to return None
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        non_existent_user_id = 999

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await mark_onboarding_as_complete(user_id=non_existent_user_id, db=mock_db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "User profile not found"

    async def test_mark_onboarding_db_error_failure(self, mock_user_with_profile, mock_db_session):
        """UTC-115-TC-03: Failure: An unexpected database error occurs during the commit operation."""
        # Arrange: Mock the query to find the profile successfully
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user_with_profile.profile
        mock_db_session.execute.return_value = mock_result
        # Arrange: Mock the commit to fail
        mock_db_session.commit.side_effect = Exception("Database connection failed")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await mark_onboarding_as_complete(user_id=mock_user_with_profile.id, db=mock_db_session)

        assert exc_info.value.status_code == 500
        # FIX: Assert the exact detail message from the production code
        assert exc_info.value.detail == "Could not update onboarding status."
        mock_db_session.rollback.assert_awaited_once()
