# src/api.py
from fastapi import APIRouter

from src.analytics.router import router as analytics_router
from src.athlete.router import router as athlete_router
from src.auth.router import router as auth_router
from src.course.router import router as course_router
from src.profile.router import router as profile_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
api_router.include_router(athlete_router, prefix="/athlete", tags=["athlete"])
api_router.include_router(course_router, prefix="/course", tags=["course"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
