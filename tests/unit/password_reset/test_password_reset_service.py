# tests/unit/password_reset/test_service.py

from unittest.mock import patch, AsyncMock, MagicMock, call, ANY
from datetime import datetime, timedelta, UTC
from collections import defaultdict
import pytest
from fastapi import HTTPException, Request

from src.auth.models import User, PasswordResetToken
from src.password_reset.schemas import ResetPasswordSchema
from src.password_reset.service import (
    get_client_ip,
    check_rate_limit,
    extract_otp_from_html,
    cleanup_expired_tokens,
    _get_and_validate_token,
    request_password_reset,
    verify_otp,
    reset_password_with_otp,
    send_email,
)
from src.password_reset.utils import generate_otp


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
def mock_user():
    """Provides a reusable mock User object."""
    return MagicMock(spec=User, id=1, email="test@example.com", password="hashed_old_password")


@pytest.fixture
def mock_password_reset_token():
    """Provides a reusable mock PasswordResetToken object."""
    return MagicMock(
        spec=PasswordResetToken,
        email="test@example.com",
        otp_hash="hashed_otp_123456",
        expires_at=datetime.now(UTC) + timedelta(minutes=15)
    )


@pytest.fixture
def mock_request():
    """Provides a reusable mock Request object."""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


# --- Test IDs: UTC-51, UTC-52, UTC-53 ---
class TestPasswordResetUtilsAndHelpers:
    """Tests for utility and helper functions in the password reset module."""

    def test_generate_otp(self):
        """UTC-51-TC-01: Success: Generate a valid 6-digit OTP string."""
        otp = generate_otp()
        assert isinstance(otp, str)
        assert len(otp) == 6
        assert otp.isdigit()

    def test_extract_otp_from_html_success(self):
        """UTC-52-TC-01: Success: Extract a 6-digit OTP from an HTML string."""
        html = "<div>Your code is: <strong>123456</strong></div>"
        assert extract_otp_from_html(html) == "123456"

    def test_extract_otp_from_html_failure(self):
        """UTC-52-TC-02: Failure: OTP pattern not found in HTML, returns fallback."""
        html = "<div>No code here.</div>"
        assert extract_otp_from_html(html) == "Check your email"

    def test_get_client_ip_direct(self, mock_request):
        """UTC-53-TC-01: Success: Get client IP from direct connection."""
        assert get_client_ip(mock_request) == "127.0.0.1"

    def test_get_client_ip_forwarded(self, mock_request):
        """UTC-53-TC-02: Success: Get client IP from X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18"}
        assert get_client_ip(mock_request) == "203.0.113.195"


# --- Test ID: UTC-54 ---
@pytest.mark.asyncio
@patch("src.password_reset.service.datetime")
class TestCheckRateLimit:
    """Tests for the check_rate_limit helper function."""

    async def test_check_rate_limit_success(self, mock_datetime):
        """UTC-54-TC-01: Success: Request is within the rate limit."""
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        store = defaultdict(list)
        identifier = "test@example.com"
        await check_rate_limit(identifier, max_requests=5, window_minutes=60, store=store)
        assert len(store[identifier]) == 1

    async def test_check_rate_limit_failure(self, mock_datetime):
        """UTC-54-TC-02: Failure: Request exceeds the rate limit."""
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        store = defaultdict(list, {"test@example.com": [datetime.now(UTC) for _ in range(5)]})
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit("test@example.com", max_requests=5, window_minutes=60, store=store)
        assert exc_info.value.status_code == 429

    async def test_check_rate_limit_cleanup_old_entries(self, mock_datetime):
        """UTC-54-TC-03: Success: Old entries are cleaned up, allowing a new request."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = now
        old_time = now - timedelta(minutes=61)
        store = defaultdict(list, {"test@example.com": [old_time, old_time]})

        await check_rate_limit("test@example.com", max_requests=2, window_minutes=60, store=store)

        assert len(store["test@example.com"]) == 1


# --- Test ID: UTC-55 ---
@pytest.mark.asyncio
class TestCleanupExpiredTokens:
    """Tests for the cleanup_expired_tokens service function."""

    async def test_cleanup_expired_tokens_deletes_records(self, mock_db_session):
        """UTC-55-TC-01: Success: Expired tokens are successfully deleted."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        await cleanup_expired_tokens(mock_db_session)

        mock_db_session.execute.assert_awaited_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_cleanup_expired_tokens_no_records_to_delete(self, mock_db_session):
        """UTC-55-TC-02: Success: No expired tokens found, commit is not called."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        await cleanup_expired_tokens(mock_db_session)

        mock_db_session.execute.assert_awaited_once()
        mock_db_session.commit.assert_not_called()


# --- Test ID: UTC-56 ---
@pytest.mark.asyncio
@patch("src.password_reset.service.verify_password")
@patch("src.password_reset.service.cleanup_expired_tokens", new_callable=AsyncMock)
class TestGetAndValidateToken:
    """Tests for the internal _get_and_validate_token helper function."""

    async def test_get_and_validate_token_success(self, mock_cleanup, mock_verify, mock_password_reset_token,
                                                  mock_db_session):
        """UTC-56-TC-01: Success: A valid, non-expired token and correct OTP are provided."""
        mock_verify.return_value = True
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_password_reset_token
        mock_db_session.execute.return_value = mock_result

        token = await _get_and_validate_token("test@example.com", "123456", mock_db_session)

        assert token == mock_password_reset_token
        mock_cleanup.assert_awaited_once()

    async def test_get_and_validate_token_not_found_failure(self, mock_cleanup, mock_verify, mock_db_session):
        """UTC-56-TC-02: Failure: No active token found for the email."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await _get_and_validate_token("test@example.com", "123456", mock_db_session)
        assert exc_info.value.status_code == 400

    async def test_get_and_validate_token_expired_failure(self, mock_cleanup, mock_verify, mock_password_reset_token,
                                                          mock_db_session):
        """UTC-56-TC-03: Failure: The token has expired."""
        mock_password_reset_token.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        mock_result_select = MagicMock()
        mock_result_select.scalars.return_value.first.return_value = mock_password_reset_token
        mock_db_session.execute.side_effect = [mock_result_select, AsyncMock()]

        with pytest.raises(HTTPException) as exc_info:
            await _get_and_validate_token("test@example.com", "123456", mock_db_session)

        assert exc_info.value.status_code == 400

    async def test_get_and_validate_token_invalid_otp_failure(self, mock_cleanup, mock_verify,
                                                              mock_password_reset_token, mock_db_session):
        """UTC-56-TC-04: Failure: The provided OTP is incorrect."""
        mock_verify.return_value = False
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_password_reset_token
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await _get_and_validate_token("test@example.com", "999999", mock_db_session)
        assert exc_info.value.status_code == 400


# --- Test ID: UTC-57 ---
@pytest.mark.asyncio
@patch("src.password_reset.service.send_email", new_callable=AsyncMock)
@patch("src.password_reset.service.hash_password")
@patch("src.password_reset.service.generate_otp")
@patch("src.password_reset.service.check_rate_limit", new_callable=AsyncMock)
@patch("src.password_reset.service.get_client_ip", return_value="127.0.0.1")
class TestRequestPasswordReset:
    """Tests for the request_password_reset service function."""

    async def test_request_password_reset_success(self, mock_get_ip, mock_rate_limit, mock_generate_otp, mock_hash,
                                                  mock_send_email, mock_user, mock_db_session):
        """UTC-57-TC-01: Success: A valid user requests a password reset."""
        mock_generate_otp.return_value = "123456"
        mock_hash.return_value = "hashed_123456"

        mock_result_user_lookup = MagicMock()
        mock_result_user_lookup.scalars.return_value.first.return_value = mock_user
        mock_db_session.execute.side_effect = [mock_result_user_lookup, AsyncMock()]

        response = await request_password_reset("test@example.com", mock_db_session, MagicMock())

        assert "a reset code has been sent" in response["message"]
        mock_send_email.assert_awaited_once()

    async def test_request_password_reset_user_not_found(self, mock_get_ip, mock_rate_limit, mock_generate_otp,
                                                         mock_hash, mock_send_email, mock_db_session):
        """UTC-57-TC-02: Success (Security): Request for a non-existent user returns a generic success message."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = await request_password_reset("notfound@example.com", mock_db_session, MagicMock())

        assert "a reset code has been sent" in response["message"]
        mock_send_email.assert_not_called()


# --- Test ID: UTC-58 ---
@pytest.mark.asyncio
@patch("src.password_reset.service._get_and_validate_token", new_callable=AsyncMock)
@patch("src.password_reset.service.check_rate_limit", new_callable=AsyncMock)
class TestVerifyOtp:
    """Tests for the verify_otp service function."""

    async def test_verify_otp_success(self, mock_rate_limit, mock_validate_token, mock_db_session):
        """UTC-58-TC-01: Success: OTP is verified successfully."""
        response = await verify_otp("test@example.com", "123456", mock_db_session, MagicMock())
        assert "confirmed successfully" in response["message"]
        mock_validate_token.assert_awaited_once_with("test@example.com", "123456", mock_db_session)

    async def test_verify_otp_invalid_token_failure(self, mock_rate_limit, mock_validate_token, mock_db_session):
        """UTC-58-TC-02: Failure: The underlying token validation fails."""
        mock_validate_token.side_effect = HTTPException(status_code=400, detail="Invalid code")
        with pytest.raises(HTTPException) as exc_info:
            await verify_otp("test@example.com", "123456", mock_db_session, MagicMock())
        assert exc_info.value.status_code == 400


# --- Test ID: UTC-59 ---
@pytest.mark.asyncio
@patch("src.password_reset.service.hash_password")
@patch("src.password_reset.service.verify_password")
@patch("src.password_reset.service._get_and_validate_token", new_callable=AsyncMock)
class TestResetPasswordWithOtp:
    """Tests for the reset_password_with_otp service function."""

    async def test_reset_password_success(self, mock_validate, mock_verify, mock_hash, mock_user, mock_db_session):
        """UTC-59-TC-01: Success: Password is reset with a valid OTP and new password."""
        mock_validate.return_value = MagicMock()
        mock_verify.return_value = False
        mock_hash.return_value = "hashed_new_password"

        mock_result_user_lookup = MagicMock()
        mock_result_user_lookup.scalars.return_value.first.return_value = mock_user
        mock_db_session.execute.side_effect = [mock_result_user_lookup, AsyncMock()]

        data = ResetPasswordSchema(email="test@example.com", otp="123456", new_password="new_password_123")
        response = await reset_password_with_otp(data, mock_db_session)

        assert "reset successfully" in response["message"]
        assert mock_user.password == "hashed_new_password"
        mock_db_session.commit.assert_awaited_once()

    async def test_reset_password_user_not_found_failure(self, mock_validate, mock_verify, mock_hash, mock_db_session):
        """UTC-59-TC-02: Failure: The user account associated with the email is not found."""
        mock_validate.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        data = ResetPasswordSchema(email="notfound@example.com", otp="123456", new_password="new_password_123")
        with pytest.raises(HTTPException) as exc_info:
            await reset_password_with_otp(data, mock_db_session)
        assert exc_info.value.status_code == 404

    async def test_reset_password_same_as_old_failure(self, mock_validate, mock_verify, mock_hash, mock_user,
                                                      mock_db_session):
        """UTC-59-TC-03: Failure: The new password is the same as the old password."""
        mock_validate.return_value = MagicMock()
        mock_verify.return_value = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        data = ResetPasswordSchema(email="test@example.com", otp="123456", new_password="old_password")
        with pytest.raises(HTTPException) as exc_info:
            await reset_password_with_otp(data, mock_db_session)
        assert exc_info.value.status_code == 400


# --- Test ID: UTC-60 ---
@pytest.mark.asyncio
@patch("src.password_reset.service.email_settings")
@patch("src.password_reset.service.EmailClient")
class TestSendEmail:
    """Tests the send_email service function."""

    async def test_send_email_success(self, mock_email_client, mock_settings):
        """UTC-60-TC-01: Success: Email is dispatched successfully."""
        mock_settings.COMMUNICATION_SERVICES_CONNECTION_STRING = "mock_connection_string"
        mock_settings.SENDER_ADDRESS = "sender@example.com"

        mock_poller = MagicMock()
        mock_poller.result.return_value = {"status": "Succeeded", "id": "some-id"}

        mock_client_instance = MagicMock()
        mock_client_instance.begin_send.return_value = mock_poller
        mock_email_client.from_connection_string.return_value = mock_client_instance

        await send_email("recipient@example.com", "Test Subject", "<html></html>")

        mock_email_client.from_connection_string.assert_called_once_with("mock_connection_string")
        mock_client_instance.begin_send.assert_called_once()
        mock_poller.result.assert_called_once()

    async def test_send_email_not_configured_failure(self, mock_email_client, mock_settings):
        """UTC-60-TC-02: Failure: Email service is not configured."""
        mock_settings.COMMUNICATION_SERVICES_CONNECTION_STRING = None

        with pytest.raises(HTTPException) as exc_info:
            await send_email("recipient@example.com", "Test Subject", "<html></html>")

        assert exc_info.value.status_code == 500
        assert "temporarily unavailable" in exc_info.value.detail
        mock_email_client.from_connection_string.assert_not_called()

    async def test_send_email_sdk_failure(self, mock_email_client, mock_settings):
        """UTC-60-TC-03: Failure: Azure SDK raises an exception during send."""
        mock_settings.COMMUNICATION_SERVICES_CONNECTION_STRING = "mock_connection_string"

        mock_client_instance = MagicMock()
        mock_client_instance.begin_send.side_effect = Exception("Azure SDK Error")
        mock_email_client.from_connection_string.return_value = mock_client_instance

        with pytest.raises(HTTPException) as exc_info:
            await send_email("recipient@example.com", "Test Subject", "<html></html>")

        assert exc_info.value.status_code == 500
        assert "Failed to send verification email" in exc_info.value.detail