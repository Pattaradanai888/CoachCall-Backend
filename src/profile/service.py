# src/profile/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, UploadFile

from src.auth.models import User
from src.auth.utils import hash_password, verify_password
from src.profile.schemas import ProfileUpdate, PasswordUpdate
from src.upload.service import image_upload_service
from src.upload.schemas import ImageType


async def update_profile(
        current_user: User,
        profile_data: ProfileUpdate,
        db: AsyncSession
) -> User:
    try:
        if not current_user.profile:
            raise HTTPException(status_code=500, detail="User profile not found.")

        if profile_data.email and profile_data.email != current_user.email:
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.email == profile_data.email))
            if result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered"
                )
            current_user.email = profile_data.email

        if profile_data.fullname is not None:
            current_user.profile.display_name = profile_data.fullname

        await db.commit()
        await db.refresh(current_user)
        return current_user

    except HTTPException:
        await db.rollback()
        raise

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


async def change_password(
        current_user: User,
        password_data: PasswordUpdate,
        db: AsyncSession
) -> None:
    # This function is correct as it only deals with the User model. No changes needed.
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation do not match"
        )
    if verify_password(password_data.new_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    try:
        current_user.password = hash_password(password_data.new_password)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )


async def upload_profile_image(
        current_user: User,
        file: UploadFile,
        db: AsyncSession
) -> str:
    try:
        if not current_user.profile:
            raise HTTPException(status_code=500, detail="User profile not found.")

        # Delete existing image if it exists on the profile
        if current_user.profile.profile_image_url:
            await image_upload_service.delete_image(current_user.profile.profile_image_url)

        upload_result = await image_upload_service.upload_image(
            file=file,
            image_type=ImageType.PROFILE,
            user_id=current_user.id
        )

        # Update profile record, not the user record
        current_user.profile.profile_image_url = upload_result.url
        await db.commit()
        await db.refresh(current_user)

        return upload_result.url

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )


async def delete_profile_image(current_user: User, db: AsyncSession) -> None:
    if not current_user.profile or not current_user.profile.profile_image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image found"
        )

    try:
        await image_upload_service.delete_image(current_user.profile.profile_image_url)

        # Update profile record
        current_user.profile.profile_image_url = None
        await db.commit()
        await db.refresh(current_user)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete profile image"
        )