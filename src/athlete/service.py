# src/athlete/service.py
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import pytz
from typing import Sequence, Optional

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import func, select, desc, update, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.upload.schemas import ImageType
from src.upload.service import image_upload_service
from .models import Athlete, Group, AthleteSkill, Position, ExperienceLevel
from .schemas import AthleteCreate, AthleteUpdate


async def create_athlete(user_id: int, athlete: AthleteCreate, db: AsyncSession):
    athlete_data = athlete.model_dump(exclude={"group_ids", "position_ids", "experience_level_id"})

    db_athlete = Athlete(**athlete_data, user_id=user_id)

    if athlete.experience_level_id is not None:
        exp_level = await db.get(ExperienceLevel, athlete.experience_level_id)
        if not exp_level or exp_level.user_id != user_id:
            raise HTTPException(status_code=400, detail=f"Invalid experience_level_id: {athlete.experience_level_id}")
        db_athlete.experience_level = exp_level

    if athlete.group_ids:
        group_results = await db.execute(
            select(Group).where(Group.id.in_(athlete.group_ids), Group.user_id == user_id)
        )
        db_athlete.groups = group_results.scalars().all()
        if len(db_athlete.groups) != len(athlete.group_ids):
            raise HTTPException(status_code=400, detail="One or more group IDs are invalid.")

    if athlete.position_ids:
        position_results = await db.execute(
            select(Position).where(Position.id.in_(athlete.position_ids), Position.user_id == user_id)
        )
        db_athlete.positions = position_results.scalars().all()
        if len(db_athlete.positions) != len(athlete.position_ids):
            raise HTTPException(status_code=400, detail="One or more position IDs are invalid.")

    db.add(db_athlete)
    await db.commit()

    await db.refresh(
        db_athlete,
        attribute_names=[
            'groups',
            'positions',
            'experience_level',
            'skill_levels'
        ]
    )
    result = await db.execute(
        select(Athlete).where(Athlete.id == db_athlete.id).options(
            selectinload(Athlete.groups),
            selectinload(Athlete.positions),
            selectinload(Athlete.experience_level),
            selectinload(Athlete.skill_levels).selectinload(AthleteSkill.skill)
        )
    )
    return result.scalars().one()


async def get_coach_athletes(user_id: int, db: AsyncSession, skip: int = 0, limit: int = 5) -> Sequence[Athlete]:
    result = await db.execute(
        select(Athlete)
        .where(Athlete.user_id == user_id)
        .order_by(desc(Athlete.created_at))  # Ordered by creation date for consistency
        .offset(skip)
        .limit(limit)
        .options(selectinload(Athlete.groups), selectinload(Athlete.positions))
    )
    return result.scalars().all()


async def get_all_coach_athletes_for_selection(user_id: int, db: AsyncSession) -> Sequence[Athlete]:
    result = await db.execute(
        select(Athlete)
        .where(Athlete.user_id == user_id)
        .order_by(Athlete.name)
        .options(
            selectinload(Athlete.positions),
            selectinload(Athlete.groups)
        )
    )
    return result.scalars().all()


async def get_coach_athlete_by_uuid(user_id: int, athlete_uuid: _uuid.UUID, db: AsyncSession):
    query = (
        select(Athlete)
        .where(Athlete.user_id == user_id, Athlete.uuid == athlete_uuid)
        .options(
            selectinload(Athlete.groups),
            selectinload(Athlete.positions),
            selectinload(Athlete.experience_level),
            selectinload(Athlete.skill_levels).selectinload(AthleteSkill.skill)
            # Load the skill levels and the skill name
        )
    )
    result = await db.execute(query)
    return result.scalars().first()


async def update_athlete(user_id: int, athlete_uuid: _uuid.UUID, athlete: AthleteUpdate, db: AsyncSession):
    # Fetch the athlete with all necessary relationships pre-loaded
    db_athlete = await get_coach_athlete_by_uuid(user_id, athlete_uuid, db)
    if not db_athlete:
        return None

    # Get data for simple fields, excluding M2M relationships
    update_data = athlete.model_dump(exclude_unset=True, exclude={'group_ids', 'position_ids'})

    # Update simple attributes
    for key, value in update_data.items():
        setattr(db_athlete, key, value)

    # Handle M2M for groups if it was included in the request
    if athlete.group_ids is not None:
        if athlete.group_ids:
            group_results = await db.execute(
                select(Group).where(Group.id.in_(athlete.group_ids), Group.user_id == user_id))
            db_athlete.groups = group_results.scalars().all()
            if len(db_athlete.groups) != len(set(athlete.group_ids)):
                raise HTTPException(status_code=400, detail="One or more group IDs are invalid.")
        else:
            db_athlete.groups = []

    # Handle M2M for positions if it was included in the request
    if athlete.position_ids is not None:
        if athlete.position_ids:
            position_results = await db.execute(
                select(Position).where(Position.id.in_(athlete.position_ids), Position.user_id == user_id))
            db_athlete.positions = position_results.scalars().all()
            if len(db_athlete.positions) != len(set(athlete.position_ids)):
                raise HTTPException(status_code=400, detail="One or more position IDs are invalid.")
        else:
            db_athlete.positions = []

    await db.commit()
    # Refresh the object and all its relationships to ensure the response is complete
    await db.refresh(
        db_athlete,
        attribute_names=[
            'groups',
            'positions',
            'experience_level',
            'skill_levels'
        ]
    )
    # Re-fetch with all nested relationships loaded for a safe return
    result = await db.execute(
        select(Athlete).where(Athlete.id == db_athlete.id).options(
            selectinload(Athlete.groups),
            selectinload(Athlete.positions),
            selectinload(Athlete.experience_level),
            selectinload(Athlete.skill_levels).selectinload(AthleteSkill.skill)
        )
    )
    return result.scalars().one()


async def delete_athlete(user_id: int, athlete_uuid: _uuid.UUID, db: AsyncSession) -> bool:
    db_athlete = await get_coach_athlete_by_uuid(user_id, athlete_uuid, db)
    if not db_athlete:
        return False

    await db.delete(db_athlete)
    await db.commit()
    return True


async def create_group(user_id: int, name: str, db: AsyncSession):
    db_group = Group(name=name, user_id=user_id)
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    return db_group


async def get_groups(user_id: int, db: AsyncSession) -> Sequence[Group]:
    result = await db.execute(select(Group).where(Group.user_id == user_id))
    return result.scalars().all()


async def delete_group(group_id: int, user_id: int, db: AsyncSession):
    result = await db.execute(select(Group).where(Group.id == group_id, Group.user_id == user_id))
    db_group = result.scalars().first()

    if not db_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Group not found or you don't have permission to delete it.")

    await db.delete(db_group)
    await db.commit()
    return {"message": "Group deleted successfully", "deleted_group_id": group_id}


async def create_position(user_id: int, name: str, db: AsyncSession):
    db_position = Position(name=name, user_id=user_id)
    db.add(db_position)
    await db.commit()
    await db.refresh(db_position)
    return db_position


async def get_positions(user_id: int, db: AsyncSession) -> Sequence[Position]:
    result = await db.execute(select(Position).where(Position.user_id == user_id))
    return result.scalars().all()


async def delete_position(position_id: int, user_id: int, db: AsyncSession):
    result = await db.execute(select(Position).where(Position.id == position_id, Position.user_id == user_id))
    db_position = result.scalars().first()

    if not db_position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Position not found or you don't have permission to delete it.")

    await db.delete(db_position)
    await db.commit()
    return {"message": "Position deleted successfully", "deleted_position_id": position_id}


async def upload_athlete_image(
        user_id: int,
        athlete_uuid: _uuid.UUID,
        file: UploadFile,
        db: AsyncSession
) -> str:
    """Upload profile image for an athlete"""
    athlete = await get_coach_athlete_by_uuid(user_id, athlete_uuid, db)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found"
        )

    try:
        # Delete existing image if it exists
        if athlete.profile_image_url:
            await image_upload_service.delete_image(athlete.profile_image_url)

        # Upload new image
        upload_result = await image_upload_service.upload_image(
            file=file,
            image_type=ImageType.ATHLETE,
            user_id=user_id,
            entity_id=athlete.id
        )

        # Update athlete record
        athlete.profile_image_url = upload_result.url
        await db.commit()
        await db.refresh(athlete)

        return upload_result.url

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload athlete image: {str(e)}"
        )


async def delete_athlete_image(user_id: int, athlete_uuid: _uuid.UUID, db: AsyncSession) -> None:
    """Delete profile image for an athlete"""
    athlete = await get_coach_athlete_by_uuid(user_id, athlete_uuid, db)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found"
        )

    if not athlete.profile_image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image found for this athlete"
        )

    try:
        # Delete from Azure storage
        await image_upload_service.delete_image(athlete.profile_image_url)

        # Update athlete record
        athlete.profile_image_url = None
        await db.commit()
        await db.refresh(athlete)

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete athlete image"
        )


async def get_latest_athlete_for_coach(user_id: int, db: AsyncSession) -> Optional[Athlete]:
    query = (
        select(Athlete)
        .where(Athlete.user_id == user_id)
        .order_by(desc(Athlete.created_at))
        .limit(1)
        .options(
            selectinload(Athlete.groups),
            selectinload(Athlete.positions)
        )
    )
    result = await db.execute(query)
    return result.scalars().first()