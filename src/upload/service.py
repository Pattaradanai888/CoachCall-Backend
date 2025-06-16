# src/upload/service.py
import io
import os
import uuid
from typing import Optional

from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import AzureError
from fastapi import HTTPException, status, UploadFile
from PIL import Image

from .config import upload_settings
from .schemas import ImageType, ImageConfig, UploadResult


class ImageUploadService:
    def __init__(self):
        self.blob_service_client = BlobServiceClient(
            account_url=f"https://{upload_settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net",
            credential=upload_settings.AZURE_STORAGE_KEY
        )

        self.configs = {
            ImageType.PROFILE: ImageConfig(
                max_width=300,
                max_height=300,
                quality=85,
                max_file_size=2 * 1024 * 1024
            ),
            ImageType.ATHLETE: ImageConfig(  # Add athlete configuration
                max_width=400,
                max_height=400,
                quality=85,
                max_file_size=3 * 1024 * 1024  # 3MB for athlete images
            ),
        }

    async def upload_image(
            self,
            file: UploadFile,
            image_type: ImageType,
            user_id: int,
            subfolder: Optional[str] = None,
            entity_id: Optional[int] = None  # For athlete images
    ) -> UploadResult:
        config = self.configs[image_type]
        container = upload_settings.PROFILE_IMAGES_CONTAINER

        self._validate_file(file, config)

        content = await file.read()

        if self._is_image_file(file.filename):
            content = self._process_image(content, config)

        blob_name = self._generate_blob_name(image_type, user_id, file.filename, subfolder, entity_id)

        url = await self._upload_to_azure(content, blob_name, container)

        return UploadResult(
            url=url,
            blob_name=blob_name,
            file_size=len(content)
        )

    async def delete_image(self, url: str) -> bool:
        try:
            container = upload_settings.PROFILE_IMAGES_CONTAINER
            blob_name = self._extract_blob_name(url)

            if not blob_name:
                return False

            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            await blob_client.delete_blob()
            return True
        except AzureError:
            return False

    def _validate_file(self, file: UploadFile, config: ImageConfig):
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in config.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(config.allowed_extensions)}"
            )

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > config.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max: {config.max_file_size // (1024 * 1024)}MB"
            )

    def _process_image(self, content: bytes, config: ImageConfig) -> bytes:
        try:
            image = Image.open(io.BytesIO(content))

            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            image.thumbnail((config.max_width, config.max_height), Image.Resampling.LANCZOS)

            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=config.quality, optimize=True)

            return img_byte_arr.getvalue()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process image: {str(e)}"
            )

    def _generate_blob_name(
            self,
            image_type: ImageType,
            user_id: int,
            filename: str,
            subfolder: Optional[str] = None,
            entity_id: Optional[int] = None
    ) -> str:
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(filename)[1].lower()

        if image_type == ImageType.PROFILE:
            base_path = "profiles"
            identifier = str(user_id)
        elif image_type == ImageType.ATHLETE:
            base_path = "athletes"
            identifier = f"{user_id}_{entity_id}" if entity_id else str(user_id)
        else:
            base_path = "uploads"
            identifier = str(user_id)

        if subfolder:
            return f"{base_path}/{subfolder}/{identifier}_{file_id}{file_ext}"
        else:
            return f"{base_path}/{identifier}_{file_id}{file_ext}"

    async def _upload_to_azure(self, content: bytes, blob_name: str, container: str) -> str:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )

            await blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="image/jpeg",
                    cache_control="public, max-age=31536000, immutable"
                )
            )

            return f"https://{upload_settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net/{container}/{blob_name}"

        except AzureError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )

    def _is_image_file(self, filename: str) -> bool:
        image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        return os.path.splitext(filename)[1].lower() in image_extensions

    def _extract_blob_name(self, url: str) -> Optional[str]:
        try:
            return '/'.join(url.split('/')[-2:])
        except:
            return None


image_upload_service = ImageUploadService()