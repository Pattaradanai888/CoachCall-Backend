# src/course/service.py

from uuid import UUID as PyUUID
from typing import Sequence, Optional, List
from fastapi import HTTPException
from sqlalchemy import select, Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.athlete.models import Athlete
from .models import Course, Session, Task, Skill, SessionTask, TaskSkillWeight
from .schemas import CourseCreate, SkillCreate


async def create_skill(user_id: int, skill_data: SkillCreate, db: AsyncSession) -> Skill:
    db_skill = Skill(**skill_data.model_dump(), user_id=user_id)
    db.add(db_skill)
    await db.commit()
    await db.refresh(db_skill)
    return db_skill


async def get_skills(user_id: int, db: AsyncSession) -> Sequence[Skill]:
    result = await db.execute(select(Skill).where(Skill.user_id == user_id))
    return result.scalars().all()


async def get_sessions(user_id: int, is_template: bool, db: AsyncSession) -> Sequence[Session]:
    query = (
        select(Session)
        .where(Session.user_id == user_id, Session.is_template == is_template)
        .options(
            selectinload(Session.tasks)
            .selectinload(SessionTask.task)
            .selectinload(Task.skill_weights)
            .selectinload(TaskSkillWeight.skill)
        )
    )
    result = await db.execute(query)
    return result.scalars().all()


async def create_course(user_id: int, course_data: CourseCreate, db: AsyncSession) -> Course:
    session_data_list = course_data.sessions
    attendee_uuids = course_data.attendee_ids

    all_skill_ids = {sw.skill_id for s in session_data_list for t in s.tasks for sw in t.skill_weights}

    valid_skills_q = await db.execute(select(Skill).where(Skill.id.in_(all_skill_ids), Skill.user_id == user_id))
    valid_skills = valid_skills_q.scalars().all()
    if len(valid_skills) != len(all_skill_ids):
        raise HTTPException(status_code=400, detail="One or more skill IDs are invalid or do not belong to you.")

    valid_attendees = []
    if attendee_uuids:
        valid_attendees_q = await db.execute(
            select(Athlete).where(Athlete.uuid.in_(attendee_uuids), Athlete.user_id == user_id))
        valid_attendees = valid_attendees_q.scalars().all()
        if len(valid_attendees) != len(set(attendee_uuids)):
            raise HTTPException(status_code=400, detail="One or more athlete IDs are invalid or do not belong to you.")

    course_create_data = course_data.model_dump(exclude={'sessions', 'attendee_ids'})

    if course_create_data.get("cover_image_url"):
        course_create_data["cover_image_url"] = str(course_create_data["cover_image_url"])

    db_course = Course(
        **course_create_data,
        user_id=user_id,
        attendees=valid_attendees
    )

    for session_data in session_data_list:
        task_data_list = session_data.tasks
        session_dict = session_data.model_dump(exclude={'tasks'})
        if session_dict.get("scheduled_date"):
            session_dict["scheduled_date"] = session_dict["scheduled_date"].replace(tzinfo=None)
        db_session = Session(
            **session_dict,
            user_id=user_id,
            course=db_course
        )

        for i, task_data in enumerate(task_data_list):
            skill_weights_data = task_data.skill_weights
            db_task = Task(
                **task_data.model_dump(exclude={'skill_weights'}),
                user_id=user_id
            )

            db_session.tasks.append(SessionTask(task=db_task, sequence=i + 1))

            for sw_data in skill_weights_data:
                db_task.skill_weights.append(TaskSkillWeight(**sw_data.model_dump()))

    db.add(db_course)
    await db.commit()

    result = await db.execute(
        select(Course)
        .where(Course.id == db_course.id)
        .options(
            selectinload(Course.attendees).selectinload(Athlete.positions),
            selectinload(Course.sessions).selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(
                Task.skill_weights).selectinload(TaskSkillWeight.skill)
        )
    )

    return result.scalars().one()


async def get_courses(user_id: int, db: AsyncSession, is_archived: bool = False) -> Sequence[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.user_id == user_id, Course.is_archived == is_archived)
        .options(selectinload(Course.attendees))
        .order_by(Course.start_date.desc())
    )
    return result.scalars().all()


async def get_all_courses_with_details(user_id: int, db: AsyncSession) -> Sequence[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.user_id == user_id)
        .options(
            selectinload(Course.sessions)
            .selectinload(Session.tasks)
            .selectinload(SessionTask.task)
            .selectinload(Task.skill_weights)
            .selectinload(TaskSkillWeight.skill),
            selectinload(Course.attendees).selectinload(Athlete.positions)
        )
        .order_by(Course.start_date.desc())
    )
    return result.scalars().all()


async def get_course_details(user_id: int, course_id: int, db: AsyncSession) -> Optional[Course]:
    query = (
        select(Course)
        .where(Course.id == course_id, Course.user_id == user_id)
        .options(
            selectinload(Course.sessions)
            .selectinload(Session.tasks)
            .selectinload(SessionTask.task)
            .selectinload(Task.skill_weights)
            .selectinload(TaskSkillWeight.skill),
            selectinload(Course.attendees).selectinload(Athlete.positions)
        )
    )
    result = await db.execute(query)
    return result.scalars().first()


async def update_course_attendees(user_id: int, course_id: int, athlete_uuids: List[PyUUID],
                                  db: AsyncSession) -> Course:
    db_course = await get_course_details(user_id, course_id, db)
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")

    if athlete_uuids:
        valid_attendees_q = await db.execute(
            select(Athlete).where(Athlete.uuid.in_(athlete_uuids), Athlete.user_id == user_id)
        )
        valid_attendees = valid_attendees_q.scalars().all()
        if len(valid_attendees) != len(set(athlete_uuids)):
            raise HTTPException(status_code=400, detail="One or more athlete IDs are invalid.")
        db_course.attendees = valid_attendees
    else:
        db_course.attendees = []

    await db.commit()
    await db.refresh(db_course, attribute_names=['attendees', 'sessions'])
    return db_course
