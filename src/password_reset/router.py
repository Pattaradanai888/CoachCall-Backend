# src/password_reset/router.py
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.password_reset import schemas, service

router = APIRouter()


@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def route_request_reset(
    payload: schemas.RequestResetSchema,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    return await service.request_password_reset(payload.email, db, request)


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def route_verify_otp(
    payload: schemas.VerifyOTPSchema,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    return await service.verify_otp(payload.email, payload.otp, db, request)


@router.post("/confirm", status_code=status.HTTP_200_OK)
async def route_reset_password(
    payload: schemas.ResetPasswordSchema, db: AsyncSession = Depends(get_async_session)
):
    return await service.reset_password_with_otp(payload, db)


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def route_cleanup_tokens(db: AsyncSession = Depends(get_async_session)):
    await service.cleanup_expired_tokens(db)
    return {"message": "Cleanup completed"}
