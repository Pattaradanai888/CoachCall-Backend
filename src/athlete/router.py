# src/athlete/router.py
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from . import service
from .schemas import (
    AthleteCreate, AthleteResponse, AthleteListResponse, AthleteUpdate, GroupResponse,
    GroupDeleteResponse, GroupCreate, PositionResponse, PositionCreate, PositionDeleteResponse,
    AthleteSelectionResponse
)
from .service import (
    create_athlete, get_coach_athletes, get_coach_athlete_by_uuid, update_athlete,
    delete_athlete, create_group, get_groups, delete_group, create_position, get_positions, delete_position,
    delete_athlete_image, upload_athlete_image, get_all_coach_athletes_for_selection
)
from ..analytics.schemas import AthleteSkillProgression
from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..course.service import update_athlete_skill_scores
from ..analytics.service import get_athlete_skill_progression

router = APIRouter()


@router.post("/groups", response_model=GroupResponse)
async def create_new_group(group_data: GroupCreate, current_user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_async_session)):
    return await create_group(current_user.id, group_data.name, db)


@router.get("/groups", response_model=List[GroupResponse])
async def list_groups(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    return await get_groups(current_user.id, db)


@router.delete("/groups/{group_id}", response_model=GroupDeleteResponse)
async def remove_group(group_id: int, current_user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_async_session)):
    return await delete_group(group_id, current_user.id, db)


@router.post("/positions", response_model=PositionResponse)
async def create_new_position(position_data: PositionCreate, current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_async_session)):
    return await create_position(current_user.id, position_data.name, db)


@router.get("/positions", response_model=List[PositionResponse])
async def list_positions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    return await get_positions(current_user.id, db)


@router.delete("/positions/{position_id}", response_model=PositionDeleteResponse)
async def remove_position(position_id: int, current_user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_async_session)):
    return await delete_position(position_id, current_user.id, db)


@router.get("/latest", response_model=Optional[AthleteListResponse])
async def get_latest_athlete(current_user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_async_session)):
    latest_athlete = await service.get_latest_athlete_for_coach(current_user.id, db)
    if not latest_athlete:
        return None

    position_names = ", ".join([p.name for p in latest_athlete.positions]) if latest_athlete.positions else "N/A"

    return AthleteListResponse(
        uuid=latest_athlete.uuid,
        name=latest_athlete.name,
        age=latest_athlete.age,
        preferred_name=latest_athlete.preferred_name,
        position=position_names,
        profile_image_url=latest_athlete.profile_image_url
    )


@router.get("/all", response_model=List[AthleteSelectionResponse])
async def list_all_athletes_for_selection(current_user: User = Depends(get_current_user),
                                          db: AsyncSession = Depends(get_async_session)):
    """Provides a lightweight list of all athletes for selection UI elements."""
    athletes = await get_all_coach_athletes_for_selection(current_user.id, db)
    return athletes


@router.get("", response_model=List[AthleteListResponse])
async def list_athletes(skip: int = 0, limit: int = 5, current_user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_async_session)):
    athletes_from_db = await get_coach_athletes(current_user.id, db, skip, limit)

    response_list = []
    for athlete in athletes_from_db:
        position_names = ", ".join([p.name for p in athlete.positions]) if athlete.positions else "N/A"
        response_list.append(
            AthleteListResponse(
                uuid=athlete.uuid,
                name=athlete.name,
                age=athlete.age,
                preferred_name=athlete.preferred_name,
                position=position_names,
                profile_image_url=athlete.profile_image_url,
            )
        )
    return response_list


@router.post("", response_model=AthleteResponse)
async def create_new_athlete(athlete: AthleteCreate, current_user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_async_session)):
    return await create_athlete(current_user.id, athlete, db)


@router.get("/{athlete_uuid}", response_model=AthleteResponse)
async def get_athlete(athlete_uuid: UUID, current_user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_async_session)):
    athlete = await get_coach_athlete_by_uuid(current_user.id, athlete_uuid, db)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return athlete


@router.get("/{athlete_uuid}/skill-progression", response_model=AthleteSkillProgression)
async def get_athlete_skills_data(
        athlete_uuid: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    return await get_athlete_skill_progression(user_id=current_user.id, athlete_uuid=athlete_uuid, db=db)


@router.post("/{athlete_uuid}/recalculate-skills", response_model=AthleteSkillProgression)
async def recalculate_athlete_skills(
        athlete_uuid: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    athlete = await get_coach_athlete_by_uuid(current_user.id, athlete_uuid, db)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    await update_athlete_skill_scores(athlete.id, db)
    await db.commit()

    return await get_athlete_skill_progression(user_id=current_user.id, athlete_uuid=athlete_uuid, db=db)


@router.put("/{athlete_uuid}", response_model=AthleteResponse)
async def update_athlete_info(athlete_uuid: UUID, athlete_update: AthleteUpdate,
                              current_user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_async_session)):
    updated = await update_athlete(current_user.id, athlete_uuid, athlete_update, db)
    if not updated:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return updated


@router.delete("/{athlete_uuid}")
async def delete_athlete_profile(athlete_uuid: UUID, current_user: User = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_async_session)):
    success = await delete_athlete(current_user.id, athlete_uuid, db)
    if not success:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return {"message": "Athlete deleted successfully"}


@router.post("/{athlete_uuid}/upload-image")
async def upload_athlete_profile_image(athlete_uuid: UUID, file: UploadFile = File(...),
                                       current_user: User = Depends(get_current_user),
                                       db: AsyncSession = Depends(get_async_session)):
    image_url = await upload_athlete_image(current_user.id, athlete_uuid, file, db)
    return {"message": "Athlete profile image uploaded successfully", "image_url": image_url}


@router.delete("/{athlete_uuid}/image")
async def delete_athlete_profile_image(athlete_uuid: UUID, current_user: User = Depends(get_current_user),
                                       db: AsyncSession = Depends(get_async_session)):
    await delete_athlete_image(current_user.id, athlete_uuid, db)
    return {"message": "Athlete profile image deleted successfully"}
