# src/course/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_async_session
from . import service
from .schemas import (
    CourseCreate, CourseRead, SkillCreate, SkillRead, CourseListRead, SessionRead, SessionTemplateRead
)
from .service import get_skills, create_skill, get_sessions, get_courses, create_course, get_all_courses_with_details, \
    get_course_details, update_course_attendees

router = APIRouter()


@router.get("/skills", response_model=List[SkillRead])
async def list_user_skills(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    return await get_skills(current_user.id, db)


@router.post("/skills", response_model=SkillRead, status_code=201)
async def create_new_skill(
        skill_data: SkillCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    return await create_skill(current_user.id, skill_data, db)


@router.get("/sessions", response_model=List[SessionTemplateRead])
async def list_sessions(
        is_template: bool = False,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    return await get_sessions(user_id=current_user.id, is_template=is_template, db=db)


@router.get("", response_model=List[CourseListRead])
async def list_courses(
        is_archived: bool = False,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    courses = await get_courses(current_user.id, db, is_archived)
    return [CourseListRead(
        id=c.id,
        name=c.name,
        start_date=c.start_date,
        end_date=c.end_date,
        attendee_count=len(c.attendees),
        is_archived=c.is_archived,
        cover_image_url=c.cover_image_url
    ) for c in courses]


@router.post("", response_model=CourseRead, status_code=201)
async def create_new_course(
        course_data: CourseCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    db_course = await create_course(current_user.id, course_data, db)
    return db_course


@router.get("/details/all", response_model=List[CourseRead])
async def get_all_course_details(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    return await get_all_courses_with_details(current_user.id, db)


@router.get("/{course_id}", response_model=CourseRead)
async def get_course_detail(
        course_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    db_course = await get_course_details(current_user.id, course_id, db)
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course


@router.put("/{course_id}/athletes", response_model=CourseRead)
async def update_course_athletes(course_id: int, athlete_uuids: List[UUID],
                                 current_user: User = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_async_session)):
    return await update_course_attendees(current_user.id, course_id, athlete_uuids, db)
