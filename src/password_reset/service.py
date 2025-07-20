# src/password_reset/service.py
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from azure.communication.email import EmailClient
from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import PasswordResetToken, User
from src.auth.utils import hash_password, verify_password
from src.config import email_settings
from src.password_reset.schemas import ResetPasswordSchema
from src.password_reset.utils import generate_otp

# Rate limiting storage (use Redis in production)
rate_limit_store: dict[str, list[datetime]] = defaultdict(list)
verification_attempts: dict[str, list[datetime]] = defaultdict(list)

# Constants
MAX_REQUESTS_PER_HOUR = 5
MAX_VERIFICATION_ATTEMPTS = 5
RATE_LIMIT_WINDOW_MINUTES = 60
VERIFICATION_WINDOW_MINUTES = 15


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    identifier: str,
    max_requests: int,
    window_minutes: int,
    store: dict[str, list[datetime]],
) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=window_minutes)

    # Clean old requests
    store[identifier] = [
        req_time for req_time in store[identifier] if req_time > cutoff
    ]

    if len(store[identifier]) >= max_requests:
        remaining_time = (
            min(store[identifier]) + timedelta(minutes=window_minutes) - now
        )
        minutes_remaining = int(remaining_time.total_seconds() / 60) + 1

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {minutes_remaining} minutes.",
        )

    store[identifier].append(now)


async def send_email(to_email: str, subject: str, html_content: str):
    if not email_settings.COMMUNICATION_SERVICES_CONNECTION_STRING:
        print("CRITICAL: Email service not configured")
        raise HTTPException(
            status_code=500, detail="Email service temporarily unavailable"
        )

    try:
        email_client = EmailClient.from_connection_string(
            email_settings.COMMUNICATION_SERVICES_CONNECTION_STRING
        )

        message = {
            "content": {
                "subject": subject,
                "html": html_content,
                "plainText": f"Your verification code is: "
                f"{extract_otp_from_html(html_content)}",
            },
            "recipients": {"to": [{"address": to_email}]},
            "senderAddress": email_settings.SENDER_ADDRESS,
        }

        poller = email_client.begin_send(message)
        result = poller.result()

        # Check if email was accepted
        if result["status"] == "Succeeded":
            print(f"Email sent successfully to {to_email} with ID: {result['id']}")
        else:
            print(f"Email send status: {result['status']}")

    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to send verification email"
        ) from e


def extract_otp_from_html(html_content: str) -> str:
    import re

    match = re.search(r"<strong>(\d{6})</strong>", html_content)
    return match.group(1) if match else "Check your email"


async def cleanup_expired_tokens(db: AsyncSession):
    now = datetime.now(UTC)
    result = await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.expires_at < now)
    )
    deleted_count = result.rowcount
    if deleted_count > 0:
        await db.commit()
        print(f"Cleaned up {deleted_count} expired tokens")


async def _get_and_validate_token(
    email: str, otp: str, db: AsyncSession
) -> PasswordResetToken:
    await cleanup_expired_tokens(db)

    token_result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.email == email)
    )
    stored_token = token_result.scalars().first()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active reset request found. Please request a new code.",
        )

    if datetime.now(UTC) > stored_token.expires_at:
        # Clean up the expired token
        await db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.email == email)
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one.",
        )

    if not verify_password(otp, stored_token.otp_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code."
        )

    return stored_token


async def request_password_reset(email: str, db: AsyncSession, request: Request = None):
    # Rate limiting by email
    await check_rate_limit(
        email, MAX_REQUESTS_PER_HOUR, RATE_LIMIT_WINDOW_MINUTES, rate_limit_store
    )

    # Additional IP-based rate limiting if request is available
    if request:
        client_ip = get_client_ip(request)
        await check_rate_limit(
            f"ip:{client_ip}",
            MAX_REQUESTS_PER_HOUR * 3,
            RATE_LIMIT_WINDOW_MINUTES,
            rate_limit_store,
        )

    # Check if user exists
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalars().first()

    # Always return success message for security
    success_message = {
        "message": "If an account with this email exists, a reset code has been sent.",
        "expires_in_minutes": email_settings.OTP_EXPIRE_MINUTES,
    }

    if not user:
        return success_message

    # Generate OTP and expiration
    otp = generate_otp()
    otp_hash = hash_password(otp)
    expires_at = datetime.now(UTC) + timedelta(
        minutes=email_settings.OTP_EXPIRE_MINUTES
    )

    # Remove old tokens and create new one
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.email == email)
    )

    token = PasswordResetToken(email=email, otp_hash=otp_hash, expires_at=expires_at)
    db.add(token)
    await db.commit()

    # Enhanced email template
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Password Reset Request</h2>
        <p>You have requested to reset your password for your CoachCall account.</p>
        <div style="background-color: #f5f5f5;
         padding: 20px; text-align: center; margin: 20px 0;">
            <h3>Your verification code is:</h3>
            <div style="font-size: 32px; font-weight: bold;
             letter-spacing: 5px; color: #2c3e50;">
                <strong>{otp}</strong>
            </div>
        </div>
        <p><strong>This code will expire in {email_settings.OTP_EXPIRE_MINUTES}
         minutes.</strong></p>
        <p style="color: #666; font-size: 14px;">
            If you didn't request this password reset,
             please ignore this email.
              Your password will remain unchanged.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
            This is an automated message from CoachCall.
             Please do not reply to this email.
        </p>
    </div>
    """

    # Send email
    await send_email(
        to_email=email,
        subject="CoachCall - Password Reset Verification Code",
        html_content=html_content,
    )

    return success_message


async def verify_otp(email: str, otp: str, db: AsyncSession, request: Request = None):
    # Rate limiting for verification attempts
    identifier = f"verify:{email}"
    if request:
        client_ip = get_client_ip(request)
        identifier = f"verify:{email}:{client_ip}"

    await check_rate_limit(
        identifier,
        MAX_VERIFICATION_ATTEMPTS,
        VERIFICATION_WINDOW_MINUTES,
        verification_attempts,
    )

    # Validate the token
    await _get_and_validate_token(email, otp, db)

    return {"message": "Verification code confirmed successfully."}


async def reset_password_with_otp(data: ResetPasswordSchema, db: AsyncSession):
    # Validate OTP first
    await _get_and_validate_token(data.email, data.otp, db)

    # Find user
    user_result = await db.execute(select(User).where(User.email == data.email))
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User account not found."
        )

    # Check if new password is different from current (optional security measure)
    if verify_password(data.new_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password.",
        )

    # Update password
    user.password = hash_password(data.new_password)

    # Clean up the used token
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.email == data.email)
    )

    await db.commit()

    # Clean up rate limiting entries for this user
    keys_to_remove = [key for key in rate_limit_store.keys() if data.email in key]
    for key in keys_to_remove:
        del rate_limit_store[key]

    keys_to_remove = [key for key in verification_attempts.keys() if data.email in key]
    for key in keys_to_remove:
        del verification_attempts[key]

    return {
        "message": "Password has been reset successfully. "
        "You can now log in with your new password."
    }
