# src/api.py
from fastapi import APIRouter
from src.auth.router import router as auth_router
from src.profile.router import router as profile_router
api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])