# tests/unit/upload/test_service.py

import io
from unittest.mock import patch, AsyncMock, MagicMock, ANY

import pytest
from azure.core.exceptions import AzureError
from fastapi import HTTPException, UploadFile

from src.upload.service import ImageUploadService
from src.upload.schemas import ImageType, UploadResult


# --- Fixtures ---

@pytest.fixture
def image_upload_service():
    """Provides a clean instance of ImageUploadService for each test."""
    with patch('src.upload.service.BlobServiceClient', new_callable=MagicMock):
        service = ImageUploadService()
        service.blob_service_client = MagicMock()
        service.blob_service_client.get_blob_client = MagicMock()
        yield service


@pytest.fixture
def mock_upload_file():
    """Creates a mock FastAPI UploadFile object."""
    file_content = b"fake image content"
    mock_file_obj = io.BytesIO(file_content)
    # To properly mock seek/tell for size validation
    mock_file_obj.seek(0, 2)
    size = mock_file_obj.tell()
    mock_file_obj.seek(0)

    mock = MagicMock(spec=UploadFile)
    mock.filename = "test_image.jpg"
    mock.file = mock_file_obj
    mock.read = AsyncMock(return_value=file_content)

    def reset_stream(*args, **kwargs):
        mock.file.seek(0)
        return mock.file.read(*args, **kwargs)

    mock.file.read = reset_stream
    return mock


# --- Test ID: UTC-42 ---
@pytest.mark.asyncio
class TestUploadImageOrchestration:
    """Tests the main upload_image method's orchestration logic."""

    @patch('src.upload.service.ImageUploadService._upload_to_azure', new_callable=AsyncMock)
    @patch('src.upload.service.ImageUploadService._generate_blob_name')
    @patch('src.upload.service.ImageUploadService._process_image')
    @patch('src.upload.service.ImageUploadService._validate_file')
    async def test_upload_image_success(
            self, mock_validate, mock_process, mock_generate, mock_upload,
            image_upload_service, mock_upload_file
    ):
        """UTC-42-TC-01: Success: Upload a valid image file."""
        mock_process.return_value = b"processed content"
        mock_generate.return_value = "generated_blob_name.jpg"
        mock_upload.return_value = "https://fake.url/generated_blob_name.jpg"

        result = await image_upload_service.upload_image(
            file=mock_upload_file, image_type=ImageType.PROFILE, user_id=1
        )

        mock_validate.assert_called_once()
        mock_process.assert_called_once()
        mock_generate.assert_called_once()
        mock_upload.assert_awaited_once_with(b"processed content", "generated_blob_name.jpg", "profile-images")
        assert isinstance(result, UploadResult)
        assert result.url == "https://fake.url/generated_blob_name.jpg"

    @patch('src.upload.service.ImageUploadService._validate_file')
    async def test_upload_image_validation_fails(self, mock_validate, image_upload_service, mock_upload_file):
        """UTC-42-TC-02: Failure: File fails validation."""
        mock_validate.side_effect = HTTPException(status_code=400, detail="Invalid file type")

        with pytest.raises(HTTPException) as exc_info:
            await image_upload_service.upload_image(
                file=mock_upload_file, image_type=ImageType.PROFILE, user_id=1
            )
        assert exc_info.value.status_code == 400
        assert "Invalid file type" in exc_info.value.detail

    @patch('src.upload.service.ImageUploadService._process_image')
    @patch('src.upload.service.ImageUploadService._validate_file')
    async def test_upload_image_processing_fails(self, mock_validate, mock_process, image_upload_service,
                                                 mock_upload_file):
        """UTC-42-TC-03: Failure: Image processing fails."""
        mock_process.side_effect = HTTPException(status_code=400, detail="Corrupt image")

        with pytest.raises(HTTPException) as exc_info:
            await image_upload_service.upload_image(
                file=mock_upload_file, image_type=ImageType.PROFILE, user_id=1
            )
        assert exc_info.value.status_code == 400
        assert "Corrupt image" in exc_info.value.detail

    @patch('src.upload.service.ImageUploadService._process_image')
    @patch('src.upload.service.ImageUploadService._upload_to_azure', new_callable=AsyncMock)
    @patch('src.upload.service.ImageUploadService._validate_file')
    async def test_upload_image_azure_fails(self, mock_validate, mock_upload, mock_process, image_upload_service,
                                            mock_upload_file):
        """UTC-42-TC-04: Failure: The final upload to Azure fails."""
        mock_upload.side_effect = HTTPException(status_code=500, detail="Azure is down")
        mock_process.return_value = b"processed content"

        with pytest.raises(HTTPException) as exc_info:
            await image_upload_service.upload_image(
                file=mock_upload_file, image_type=ImageType.PROFILE, user_id=1
            )
        assert exc_info.value.status_code == 500
        assert "Azure is down" in exc_info.value.detail

    @patch('src.upload.service.ImageUploadService._process_image')
    @patch('src.upload.service.ImageUploadService._is_image_file', return_value=False)
    @patch('src.upload.service.ImageUploadService._validate_file')
    async def test_upload_non_image_file_skips_processing(
            self, mock_validate, mock_is_image, mock_process, image_upload_service, mock_upload_file
    ):
        """UTC-42-TC-05: Success: Upload a valid non-image file (e.g., a document)."""
        mock_upload_file.filename = "document.pdf"

        mock_generate_blob = MagicMock(return_value="some_blob_name.pdf")
        mock_upload_azure = AsyncMock(return_value="http://fake.url/some_blob_name.pdf")

        with patch.multiple(image_upload_service, _generate_blob_name=mock_generate_blob,
                            _upload_to_azure=mock_upload_azure):
            await image_upload_service.upload_image(
                file=mock_upload_file, image_type=ImageType.PROFILE, user_id=1
            )
            mock_process.assert_not_called()


# --- Test ID: UTC-43 ---
@pytest.mark.asyncio
class TestDeleteImage:
    """Tests the delete_image method."""

    async def test_delete_image_success(self, image_upload_service):
        """UTC-43-TC-01: Success: Delete an existing image."""
        mock_blob_client = MagicMock()
        mock_blob_client.delete_blob = AsyncMock()
        image_upload_service.blob_service_client.get_blob_client.return_value = mock_blob_client

        url = "https://fake.blob.core.windows.net/profile-images/profiles/1_uuid.jpg"
        result = await image_upload_service.delete_image(url)

        assert result is True
        mock_blob_client.delete_blob.assert_awaited_once()

    async def test_delete_image_azure_error(self, image_upload_service):
        """UTC-43-TC-02: Failure: Azure SDK fails during deletion."""
        mock_blob_client = MagicMock()
        mock_blob_client.delete_blob = AsyncMock(side_effect=AzureError("Connection failed"))
        image_upload_service.blob_service_client.get_blob_client.return_value = mock_blob_client

        url = "https://fake.blob.core.windows.net/profile-images/profiles/1_uuid.jpg"
        result = await image_upload_service.delete_image(url)

        assert result is False

    async def test_delete_image_invalid_url(self, image_upload_service):
        """UTC-43-TC-03: Failure: The provided URL is invalid or malformed."""
        url = "https://other.storage/wrong-container/blob.jpg"
        result = await image_upload_service.delete_image(url)

        assert result is False
        image_upload_service.blob_service_client.get_blob_client.assert_not_called()


# --- Test ID: UTC-44 ---
class TestInternalHelpers:
    """Tests the internal helper methods _validate_file and _process_image."""

    def test_validate_file_success(self, image_upload_service, mock_upload_file):
        """UTC-44-TC-01: Success: _validate_file passes for a valid file."""
        try:
            config = image_upload_service.configs[ImageType.PROFILE]
            image_upload_service._validate_file(mock_upload_file, config)
        except HTTPException:
            pytest.fail("_validate_file raised HTTPException unexpectedly.")

    def test_validate_file_bad_extension(self, image_upload_service, mock_upload_file):
        """UTC-44-TC-02: Failure: _validate_file fails due to invalid file extension."""
        mock_upload_file.filename = "document.txt"
        config = image_upload_service.configs[ImageType.PROFILE]
        with pytest.raises(HTTPException) as exc_info:
            image_upload_service._validate_file(mock_upload_file, config)
        assert "Invalid file type" in exc_info.value.detail

    def test_validate_file_too_large(self, image_upload_service, mock_upload_file):
        """UTC-44-TC-03: Failure: _validate_file fails due to excessive file size."""
        config = image_upload_service.configs[ImageType.PROFILE]
        config.max_file_size = 10  # 10 bytes
        with pytest.raises(HTTPException) as exc_info:
            image_upload_service._validate_file(mock_upload_file, config)
        assert "File too large" in exc_info.value.detail

    @patch('src.upload.service.Image')
    def test_process_image_success(self, mock_pil_image, image_upload_service):
        """UTC-44-TC-04: Success: _process_image correctly resizes and converts an image."""
        mock_image_instance = MagicMock()
        mock_image_instance.mode = "RGBA"
        mock_image_instance.size = (2000, 1500)

        mock_image_instance.convert.return_value = mock_image_instance

        mock_pil_image.open.return_value = mock_image_instance
        config = image_upload_service.configs[ImageType.COURSE]

        result_bytes = image_upload_service._process_image(b"fake content", config)

        mock_pil_image.open.assert_called_once()
        mock_image_instance.convert.assert_called_once_with("RGB")
        mock_image_instance.thumbnail.assert_called_with(
            (config.max_width, config.max_height), ANY
        )
        mock_image_instance.save.assert_called_once()
        assert isinstance(result_bytes, bytes)

    @patch('src.upload.service.Image.open')
    def test_process_image_pil_fails(self, mock_pil_open, image_upload_service):
        """UTC-44-TC-05: Failure: _process_image fails on a corrupt image file."""
        mock_pil_open.side_effect = Exception("Corrupt file")
        config = image_upload_service.configs[ImageType.PROFILE]
        with pytest.raises(HTTPException) as exc_info:
            image_upload_service._process_image(b"corrupt content", config)
        assert "Failed to process image" in exc_info.value.detail


# --- Test ID: UTC-45 ---
@patch('src.upload.service.uuid.uuid4')
class TestNamingHelpers:
    """Tests the pure helper functions for generating and parsing blob names."""

    def test_generate_blob_name_profile(self, mock_uuid, image_upload_service):
        """UTC-45-TC-01: Success: _generate_blob_name for a profile image."""
        mock_uuid.return_value = "fake-uuid"
        blob_name = image_upload_service._generate_blob_name(
            image_type=ImageType.PROFILE, user_id=123, filename="avatar.png"
        )
        assert blob_name == "profiles/123_fake-uuid.png"

    def test_generate_blob_name_course(self, mock_uuid, image_upload_service):
        """UTC-45-TC-02: Success: _generate_blob_name for a course image."""
        mock_uuid.return_value = "fake-uuid"
        blob_name = image_upload_service._generate_blob_name(
            image_type=ImageType.COURSE, user_id=123, entity_id=45, filename="header.jpg"
        )
        assert blob_name == "courses/123_45_fake-uuid.jpg"

    def test_generate_blob_name_athlete_with_subfolder(self, mock_uuid, image_upload_service):
        """UTC-45-TC-03: Success: _generate_blob_name for an athlete image with a subfolder."""
        mock_uuid.return_value = "fake-uuid"
        blob_name = image_upload_service._generate_blob_name(
            image_type=ImageType.ATHLETE, user_id=123, entity_id=789,
            subfolder="action_shots", filename="dunk.jpeg"
        )
        assert blob_name == "athletes/action_shots/123_789_fake-uuid.jpeg"

    @patch('src.upload.service.upload_settings')
    def test_extract_blob_name_success(self, mock_settings, mock_uuid, image_upload_service):
        """UTC-45-TC-04: Success: _extract_blob_name parses a valid URL."""
        mock_settings.PROFILE_IMAGES_CONTAINER = "test-container"
        url = "https://fake.blob.core.windows.net/test-container/profiles/123_uuid.jpg"
        blob_name = image_upload_service._extract_blob_name(url)
        assert blob_name == "profiles/123_uuid.jpg"

    @patch('src.upload.service.upload_settings')
    def test_extract_blob_name_different_container(self, mock_settings, mock_uuid, image_upload_service):
        """UTC-45-TC-05: Failure: _extract_blob_name on a URL with a different container."""
        mock_settings.PROFILE_IMAGES_CONTAINER = "correct-container"
        url = "https://fake.blob.core.windows.net/wrong-container/profiles/123_uuid.jpg"
        blob_name = image_upload_service._extract_blob_name(url)
        assert blob_name is None