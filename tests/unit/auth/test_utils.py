# tests/unit/auth/test_utils.py
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from src.auth.config import auth_settings
from src.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# --- Test ID: UTC-05 ---
class TestPasswordUtils:
    def test_hash_and_verify_success(self):
        """UTC-05-TC-01: Verify a correct password against its hash."""
        password = "S3curePa$$w0rd"
        hashed_password = hash_password(password)

        # 1. hash_password returns a string that is not equal to the input password.
        assert isinstance(hashed_password, str)
        assert hashed_password != password

        # 2. verify_password returns True.
        assert verify_password(password, hashed_password) is True

    def test_verify_failure(self):
        """UTC-05-TC-02: Verify an incorrect password against a hash."""
        correct_password = "S3curePa$$w0rd"
        wrong_password = "WrongPassword"
        hashed_password = hash_password(correct_password)

        # 1. verify_password returns False.
        assert verify_password(wrong_password, hashed_password) is False


# --- Test ID: UTC-06 ---
class TestTokenUtils:
    def test_create_and_decode_token_success(self):
        """UTC-06-TC-01: Create and decode a valid access token."""
        data = {"sub": "test@user.com", "custom": "data"}

        # 1. create_access_token returns a three-part JWT string.
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

        # 2. decode_access_token(token) returns a payload dictionary.
        payload = decode_access_token(token)

        # 3. The decoded payload contains the sub and custom fields.
        assert payload["sub"] == "test@user.com"
        assert payload["custom"] == "data"

        # 4. The decoded payload contains an exp (expiration) claim.
        assert "exp" in payload

        # Also test refresh token creation for completeness
        refresh_token = create_refresh_token(data)
        assert isinstance(refresh_token, str)

    def test_decode_expired_token(self):
        """UTC-06-TC-02: Decode an expired token."""
        # Create a token that expired 1 minute ago
        expire = datetime.utcnow() - timedelta(minutes=1)
        expired_token = jwt.encode(
            {"sub": "test", "exp": expire},
            auth_settings.JWT_SECRET,
            algorithm=auth_settings.JWT_ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has expired"

    def test_decode_invalid_signature(self):
        """UTC-06-TC-03: Decode a token with an invalid signature."""
        token = create_access_token({"sub": "test"})
        wrong_secret = "a-completely-different-and-wrong-secret-key-that-is-long"

        # Patch the settings to use the wrong secret for decoding
        with patch("src.auth.utils.auth_settings.JWT_SECRET", wrong_secret):
            with pytest.raises(HTTPException) as exc_info:
                decode_access_token(token)

        assert exc_info.value.status_code == 401
        assert "Signature verification failed" in exc_info.value.detail

    def test_decode_malformed_token(self):
        """UTC-06-TC-04: Decode a malformed token."""
        token = "not.a.valid.token"

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401
        assert "Could not validate token" in exc_info.value.detail