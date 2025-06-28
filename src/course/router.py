# src/course/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_async_session
from .schemas import (
    CourseCreate, CourseRead, SkillCreate, SkillRead, CourseListRead, SessionRead, SessionTemplateRead, SessionCreate,
    SessionCompletionPayload, SessionStatusUpdate, SessionReportData
)
from .service import (
    get_skills, create_skill, get_sessions, create_course, get_all_courses_with_details,
    get_course_details, update_course_attendees, create_session, get_courses, save_task_completions,
    update_session_status, get_session_report_data, upload_course_image, update_session
)
from ..upload.schemas import UploadResponse

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


@router.get("/sessions", response_model=List[SessionRead])
async def list_sessions(
        is_template: bool = False,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    sessions = await get_sessions(user_id=current_user.id, is_template=is_template, db=db)
    return sessions


@router.post("/sessions", response_model=SessionRead, status_code=201)
async def create_new_session(
        session_data: SessionCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    return await create_session(user_id=current_user.id, session_data=session_data, db=db)


@router.put("/sessions/{session_id}", response_model=SessionRead)
async def update_existing_session(
        session_id: int,
        session_data: SessionCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Update a session template by its ID."""
    return await update_session(user_id=current_user.id, session_id=session_id, session_data=session_data, db=db)


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


@router.post("/{course_id}/upload-image", response_model=UploadResponse)
async def upload_a_course_cover_image(
        course_id: int,
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """Endpoint to upload a cover image for a specific course."""
    image_url = await upload_course_image(
        user_id=current_user.id,
        course_id=course_id,
        file=file,
        db=db
    )
    return {"url": image_url}


@router.put("/{course_id}/athletes", response_model=CourseRead)
async def update_course_athletes(course_id: int, athlete_uuids: List[UUID],
                                 current_user: User = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_async_session)):
    return await update_course_attendees(current_user.id, course_id, athlete_uuids, db)


@router.put("/{course_id}/athletes", response_model=CourseRead)
async def update_course_athletes(course_id: int, athlete_uuids: List[UUID],
                                 current_user: User = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_async_session)):
    return await update_course_attendees(current_user.id, course_id, athlete_uuids, db)


@router.put("/session/{session_id}/status", response_model=SessionRead)
async def update_a_session_status(
        session_id: int,
        status_update: SessionStatusUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    updated_session = await update_session_status(
        user_id=current_user.id,
        session_id=session_id,
        new_status=status_update.status,
        db=db
    )

    if not updated_session:
        raise HTTPException(status_code=404, detail="Session not found or you do not have permission.")

    return updated_session


@router.get("/session/{session_id}/report", response_model=SessionReportData)
async def get_session_report(
        session_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    report_data = await get_session_report_data(user_id=current_user.id, session_id=session_id, db=db)
    if not report_data:
        raise HTTPException(status_code=404, detail="Session report not found or session is not complete.")
    return report_data


@router.post("/session/{session_id}/complete", status_code=201)
async def complete_session_and_save_scores(
        session_id: int,
        payload: SessionCompletionPayload,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    await save_task_completions(user_id=current_user.id, session_id=session_id, payload=payload, db=db)
    return {"message": "Session scores saved successfully."}
