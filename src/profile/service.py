# src/profile/service.py
import os
import io
from typing import Optional

from azure.storage.blob import ContentSettings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, UploadFile
from PIL import Image
import uuid
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import AzureError

from src.auth.models import User
from src.auth.utils import hash_password, verify_password
from src.profile.schemas import ProfileUpdate, PasswordUpdate
from src.profile.config import azure_settings

# Configuration
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_SIZE = (300, 300)  # Profile image size


class AzureBlobService:
    def __init__(self):
        self.blob_service_client = BlobServiceClient(
            account_url=f"https://{azure_settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net",
            credential=azure_settings.AZURE_STORAGE_KEY
        )
        self.container_name = azure_settings.AZURE_CONTAINER_NAME

    async def upload_image(self, image_data: bytes, blob_name: str) -> str:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )

            await blob_client.upload_blob(
                image_data,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="image/jpeg",
                    cache_control="public, max-age=31536000, immutable"
                )
            )

            # Return the public URL
            return f"https://{azure_settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net/{self.container_name}/{blob_name}"

        except AzureError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload image to Azure: {str(e)}"
            )

    async def delete_image(self, blob_name: str) -> bool:
        """Delete image from Azure Blob Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            await blob_client.delete_blob()
            return True
        except AzureError:
            return False

    def extract_blob_name_from_url(self, url: str) -> Optional[str]:
        """Extract blob name from Azure blob URL"""
        try:
            parts = url.split('/')
            if len(parts) >= 2:
                return '/'.join(parts[-2:])
            return None
        except Exception:
            return None


# Initialize Azure Blob Service
azure_blob_service = AzureBlobService()


async def update_profile(
        current_user: User,
        profile_data: ProfileUpdate,
        db: AsyncSession
) -> User:
    """Update user profile information"""

    try:
        # Check email uniqueness if being changed
        if profile_data.email and profile_data.email != current_user.email:
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.email == profile_data.email)
            )
            if result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered"
                )
            current_user.email = profile_data.email

        # Update fullname if provided
        if profile_data.fullname is not None:
            current_user.fullname = profile_data.fullname

        await db.commit()
        await db.refresh(current_user)
        return current_user

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
            detail="Failed to update profile"
        )


async def change_password(
        current_user: User,
        password_data: PasswordUpdate,
        db: AsyncSession
) -> None:

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

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5MB"
        )

    try:
        # Process and resize image
        image = Image.open(io.BytesIO(content))

        # Convert to RGB if necessary (for PNG with transparency)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Resize image
        image.thumbnail(IMAGE_SIZE, Image.Resampling.LANCZOS)

        # Convert processed image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=85, optimize=True)
        processed_image_data = img_byte_arr.getvalue()

        # Generate unique blob name
        file_id = str(uuid.uuid4())
        blob_name = f"profiles/{current_user.id}_{file_id}.jpg"

        # Delete old profile image if exists
        if hasattr(current_user, 'profile_image_url') and current_user.profile_image_url:
            old_blob_name = azure_blob_service.extract_blob_name_from_url(
                current_user.profile_image_url
            )
            if old_blob_name:
                await azure_blob_service.delete_image(old_blob_name)

        # Upload to Azure Blob Storage
        image_url = await azure_blob_service.upload_image(processed_image_data, blob_name)

        current_user.profile_image_url = image_url
        await db.commit()
        await db.refresh(current_user)

        return image_url

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process image: {str(e)}"
        )

async def delete_profile_image(current_user: User, db: AsyncSession) -> None:
    if not hasattr(current_user, 'profile_image_url') or not current_user.profile_image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image found"
        )

    try:
        # Extract blob name and delete from storage
        blob_name = azure_blob_service.extract_blob_name_from_url(
            current_user.profile_image_url
        )
        if blob_name:
            await azure_blob_service.delete_image(blob_name)

        # Update database
        current_user.profile_image_url = None
        await db.commit()
        await db.refresh(current_user)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete profile image"
        )