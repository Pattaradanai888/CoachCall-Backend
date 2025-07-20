# src/analytics/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_async_session

from . import service
from .schemas import AthleteCreationStat, CoachStatData

router = APIRouter()


@router.get("/athletes/stats", response_model=AthleteCreationStat)
async def get_athlete_creation_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await service.get_athlete_stats(current_user.id, db)


@router.get("/coach-stats/all", response_model=CoachStatData)
async def get_coach_efficiency_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await service.get_coach_dashboard_stats(current_user.id, db)
