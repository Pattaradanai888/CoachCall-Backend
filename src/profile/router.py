# src/profile/router.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.auth.schemas import UserProfileRead
from src.database import get_async_session
from src.profile.schemas import PasswordUpdate, ProfileResponse, ProfileUpdate
from src.profile.service import (
    change_password,
    delete_profile_image,
    mark_onboarding_as_complete,
    update_profile,
    upload_profile_image,
)

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        fullname=current_user.profile.display_name,
        profile_image_url=current_user.profile.profile_image_url,
    )


@router.put("/me", response_model=ProfileResponse)
async def update_user_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    updated_user = await update_profile(current_user, profile_data, db)
    if not updated_user.profile:
        raise HTTPException(
            status_code=404, detail="User profile not found after update"
        )

    return ProfileResponse(
        id=updated_user.id,
        email=updated_user.email,
        fullname=updated_user.profile.display_name,
        profile_image_url=updated_user.profile.profile_image_url,
    )


@router.post("/change-password")
async def change_user_password(
    password_data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await change_password(current_user, password_data, db)
    return {"message": "Password changed successfully"}


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    image_url = await upload_profile_image(current_user, file, db)
    return {"message": "Profile image uploaded successfully", "image_url": image_url}


@router.delete("/image")
async def delete_image(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await delete_profile_image(current_user, db)
    return {"message": "Profile image deleted successfully"}


@router.put(
    "/onboarding-complete",
    response_model=UserProfileRead,
    status_code=status.HTTP_200_OK,
)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    updated_profile = await mark_onboarding_as_complete(user_id=current_user.id, db=db)

    if not updated_profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update onboarding status.",
        )

    return updated_profile
