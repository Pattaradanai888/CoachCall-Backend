# src/athlete/service.py
import uuid as _uuid
from datetime import datetime, timedelta, timezone
import pytz
from typing import Sequence, Optional

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import func, select, desc, update
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

    # Eagerly load all relationships needed for the response to prevent MissingGreenlet error
    await db.refresh(
        db_athlete,
        attribute_names=[
            'groups',
            'positions',
            'experience_level',
            'skill_levels'
        ]
    )
    # The related skill objects for skill_levels might also need to be loaded
    # if they are accessed in the response model. Let's load them explicitly.
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


async def get_athlete_stats(user_id: int, db: AsyncSession):
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date()

    # Time periods
    seven_days_ago = today_utc - timedelta(days=7)
    month_ago = today_utc - timedelta(days=30)
    six_days_ago = today_utc - timedelta(days=6)

    # Convert to datetime for comparison
    today_start = datetime.combine(today_utc, datetime.min.time(), tzinfo=timezone.utc)
    seven_days_ago_start = datetime.combine(seven_days_ago, datetime.min.time(), tzinfo=timezone.utc)
    six_days_ago_start = datetime.combine(six_days_ago, datetime.min.time(), tzinfo=timezone.utc)
    month_start = datetime.combine(month_ago, datetime.min.time(), tzinfo=timezone.utc)

    # Basic counts
    today_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id,
            Athlete.created_at >= today_start
        )
    )

    week_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id,
            Athlete.created_at >= seven_days_ago_start
        )
    )

    month_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id,
            Athlete.created_at >= month_start
        )
    )

    # Total athletes
    total_athletes = await db.scalar(
        select(func.count(Athlete.id)).where(Athlete.user_id == user_id)
    )

    # Get daily counts for the past 7 days
    daily_counts_query = select(
        func.date(Athlete.created_at).label('date'),
        func.count(Athlete.id).label('count')
    ).where(
        Athlete.user_id == user_id,
        Athlete.created_at >= six_days_ago_start
    ).group_by(func.date(Athlete.created_at)).order_by(func.date(Athlete.created_at))

    daily_counts_result = await db.execute(daily_counts_query)
    daily_counts = daily_counts_result.all()

    # Create detailed trend data
    daily_counts_dict = {row.date: row.count for row in daily_counts}
    dates = [six_days_ago + timedelta(days=i) for i in range(7)]

    # Enhanced trend data with dates and day names
    trend_data = []
    for date in dates:
        count = daily_counts_dict.get(date, 0)
        trend_data.append({
            "date": date.isoformat(),
            "day_name": date.strftime("%a"),  # Mon, Tue, etc.
            "formatted_date": date.strftime("%m/%d"),  # 12/25
            "count": count
        })

    # Calculate percentage changes for insights
    prev_week_start = seven_days_ago - timedelta(days=7)
    prev_week_start_dt = datetime.combine(prev_week_start, datetime.min.time())

    prev_week_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id,
            Athlete.created_at >= prev_week_start_dt,
            Athlete.created_at < seven_days_ago_start
        )
    )

    # Calculate week-over-week change - handle None values properly
    week_change = None
    is_growing = None
    if prev_week_count is not None and prev_week_count > 0:
        week_change = round(((week_count - prev_week_count) / prev_week_count) * 100, 1)
        is_growing = week_change > 0
    elif prev_week_count == 0 and week_count > 0:
        # If previous week had 0 and current week has some, it's growing
        is_growing = True
        week_change = 100.0  # or you could set this to None if you prefer

    # Find peak day in current week
    peak_day = None
    max_count = 0
    for item in trend_data:
        if item["count"] > max_count:
            max_count = item["count"]
            peak_day = item["day_name"]

    # Only set peak_day if there's actual data
    if max_count == 0:
        peak_day = None

    # Calculate average daily additions
    avg_daily = round(week_count / 7, 1) if week_count > 0 else 0.0

    stats = {
        "today": today_count or 0,
        "week": week_count or 0,
        "month": month_count or 0,
        "total": total_athletes or 0,
        "trend": [item["count"] for item in trend_data],
        "trend_detailed": trend_data,
        "insights": {
            "week_change_percent": week_change,  # Can be None
            "peak_day": peak_day,  # Can be None
            "avg_daily": avg_daily,  # Always float
            "is_growing": is_growing  # Can be None
        }
    }
    return stats


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