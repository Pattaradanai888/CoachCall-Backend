# src/course/service.py

from typing import Sequence, Optional, List
from uuid import UUID as PyUUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.athlete.models import Athlete
from .models import Course, Session, Task, Skill, SessionTask, TaskSkillWeight, TaskCompletion
from .schemas import CourseCreate, SkillCreate, SessionCreate, SessionCompletionPayload, EventItem, \
    CourseArchiveStatusUpdate
from ..upload.schemas import ImageType
from ..upload.service import image_upload_service


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
            .selectinload(TaskSkillWeight.skill),
            selectinload(Session.completions).selectinload(TaskCompletion.athlete)
        )
    )
    result = await db.execute(query)
    return result.scalars().unique().all()


async def create_session(user_id: int, session_data: SessionCreate, db: AsyncSession) -> Session:
    all_skill_ids = {sw.skill_id for t in session_data.tasks for sw in t.skill_weights}
    if all_skill_ids:
        valid_skills_q = await db.execute(select(Skill).where(Skill.id.in_(all_skill_ids), Skill.user_id == user_id))
        if len(valid_skills_q.scalars().all()) != len(all_skill_ids):
            raise HTTPException(status_code=400, detail="One or more skill IDs are invalid.")

    task_data_list = session_data.tasks
    session_dict = session_data.model_dump(exclude={'tasks'})

    if session_dict.get("scheduled_date"):
        session_dict["scheduled_date"] = session_dict["scheduled_date"].replace(tzinfo=None)

    db_session = Session(**session_dict, user_id=user_id)

    for i, task_data in enumerate(task_data_list):
        skill_weights_data = task_data.skill_weights
        db_task = Task(
            **task_data.model_dump(exclude={'skill_weights'}),
            user_id=user_id
        )
        db_session.tasks.append(SessionTask(task=db_task, sequence=i + 1))
        for sw_data in skill_weights_data:
            db_task.skill_weights.append(TaskSkillWeight(**sw_data.model_dump()))

    db.add(db_session)
    await db.commit()
    result = await db.execute(
        select(Session)
        .where(Session.id == db_session.id)
        .options(
            selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(
                Task.skill_weights).selectinload(TaskSkillWeight.skill),
            selectinload(Session.completions).selectinload(TaskCompletion.athlete)
        )
    )
    return result.scalars().unique().one()


async def update_session(user_id: int, session_id: int, session_data: SessionCreate, db: AsyncSession) -> Session:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
        .options(selectinload(Session.tasks))
    )
    db_session = result.scalars().unique().one_or_none()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found or you do not have permission.")

    db_session.name = session_data.name
    db_session.description = session_data.description

    db_session.tasks.clear()
    await db.flush()

    for i, task_data in enumerate(session_data.tasks):
        skill_weights_data = task_data.skill_weights
        db_task = Task(
            **task_data.model_dump(exclude={'skill_weights'}),
            user_id=user_id
        )
        session_task_link = SessionTask(task=db_task, sequence=i + 1)

        for sw_data in skill_weights_data:
            db_task.skill_weights.append(TaskSkillWeight(**sw_data.model_dump()))

        db_session.tasks.append(session_task_link)

    await db.commit()

    result = await db.execute(
        select(Session)
        .where(Session.id == db_session.id)
        .options(
            selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(
                Task.skill_weights).selectinload(TaskSkillWeight.skill),
            selectinload(Session.completions).selectinload(TaskCompletion.athlete)
        )
    )
    return result.scalars().unique().one()


async def delete_session(user_id: int, session_id: int, db: AsyncSession) -> None:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    db_session = result.scalars().one_or_none()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session template not found.")

    await db.delete(db_session)
    await db.commit()
    return


async def create_course(user_id: int, course_data: CourseCreate, db: AsyncSession) -> Course:
    session_data_list = course_data.sessions
    attendee_uuids = course_data.attendee_ids

    all_skill_ids = {sw.skill_id for s in session_data_list for t in s.tasks for sw in t.skill_weights}

    if all_skill_ids:
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
            selectinload(Course.sessions).options(
                selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(
                    Task.skill_weights).selectinload(TaskSkillWeight.skill),
                # *** FIX 1: Eagerly load the athlete for each completion ***
                selectinload(Session.completions).selectinload(TaskCompletion.athlete)
            )
        )
    )

    return result.scalars().unique().one()


async def get_courses(user_id: int, db: AsyncSession, is_archived: bool = False) -> Sequence[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.user_id == user_id, Course.is_archived == is_archived)
        .options(selectinload(Course.attendees))
        .order_by(Course.start_date.desc(), Course.id.desc())
    )
    return result.scalars().all()


async def get_all_courses_with_details(user_id: int, db: AsyncSession) -> Sequence[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.user_id == user_id)
        .options(
            selectinload(Course.sessions).options(
                selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(
                    Task.skill_weights).selectinload(TaskSkillWeight.skill),
                selectinload(Session.completions).selectinload(TaskCompletion.athlete)
            ),
            selectinload(Course.attendees).selectinload(Athlete.positions)
        )
        .order_by(Course.start_date.desc(), Course.id.desc())
    )
    return result.scalars().unique().all()


async def get_course_details(user_id: int, course_id: int, db: AsyncSession) -> Optional[Course]:
    query = (
        select(Course)
        .where(Course.id == course_id, Course.user_id == user_id)
        .options(
            selectinload(Course.sessions).options(
                selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(
                    Task.skill_weights).selectinload(TaskSkillWeight.skill),
                # *** FIX 3: Eagerly load the athlete for each completion ***
                selectinload(Session.completions).selectinload(TaskCompletion.athlete)
            ),
            selectinload(Course.attendees).selectinload(Athlete.positions)
        )
    )
    result = await db.execute(query)
    return result.scalars().unique().one_or_none()


async def update_course(user_id: int, course_id: int, course_data: CourseCreate, db: AsyncSession) -> Course:
    db_course = await get_course_details(user_id, course_id, db)
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found or you don't have permission to edit it.")

    update_data = course_data.model_dump(exclude={'sessions', 'attendee_ids', 'title', 'cover_image_url'})
    db_course.name = course_data.name
    for key, value in update_data.items():
        setattr(db_course, key, value)

    if course_data.cover_image_url:
        db_course.cover_image_url = str(course_data.cover_image_url)

    if course_data.attendee_ids is not None:
        if course_data.attendee_ids:
            valid_attendees_q = await db.execute(
                select(Athlete).where(Athlete.uuid.in_(course_data.attendee_ids), Athlete.user_id == user_id)
            )
            db_course.attendees = valid_attendees_q.scalars().all()
        else:
            db_course.attendees = []

    db_course.sessions.clear()
    await db.flush()

    for session_data in course_data.sessions:
        task_data_list = session_data.tasks
        session_dict = session_data.model_dump(exclude={'tasks'})
        if session_dict.get("scheduled_date"):
            session_dict["scheduled_date"] = session_dict["scheduled_date"].replace(tzinfo=None)

        db_session = Session(
            **session_dict,
            user_id=user_id,
            course_id=db_course.id
        )

        for i, task_data in enumerate(task_data_list):
            skill_weights_data = task_data.skill_weights
            db_task = Task(
                **task_data.model_dump(exclude={'skill_weights'}),
                user_id=user_id
            )
            session_task_link = SessionTask(task=db_task, sequence=i + 1)
            db_session.tasks.append(session_task_link)

            for sw_data in skill_weights_data:
                db_task.skill_weights.append(TaskSkillWeight(**sw_data.model_dump()))

        db.add(db_session)

    await db.commit()

    updated_course = await get_course_details(user_id, course_id, db)
    if not updated_course:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated course.")

    return updated_course


async def delete_course(user_id: int, course_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.user_id == user_id)
    )
    db_course = result.scalars().one_or_none()

    if not db_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found or you do not have permission to delete it."
        )

    await db.delete(db_course)
    await db.commit()

    return {"message": "Course deleted successfully", "deleted_course_id": course_id}


async def update_course_archive_status(user_id: int, course_id: int, status_update: CourseArchiveStatusUpdate,
                                       db: AsyncSession) -> Course:
    stmt = (
        update(Course)
        .where(Course.id == course_id, Course.user_id == user_id)
        .values(is_archived=status_update.is_archived)
    )
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found or you do not have permission."
        )

    await db.commit()

    updated_course = await get_course_details(user_id=user_id, course_id=course_id, db=db)
    if not updated_course:
        raise HTTPException(status_code=500, detail="Could not retrieve updated course details.")

    return updated_course


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

    updated_course = await get_course_details(user_id, course_id, db)
    if not updated_course:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated course details after update.")

    return updated_course


async def update_session_status(user_id: int, session_id: int, new_status: str, db: AsyncSession) -> Session | None:
    subquery = select(Session.id).where(Session.id == session_id, Session.user_id == user_id).scalar_subquery()

    await db.execute(
        update(Session)
        .where(Session.id == subquery)
        .values(status=new_status)
    )
    await db.commit()

    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .options(
            selectinload(Session.tasks)
            .selectinload(SessionTask.task)
            .selectinload(Task.skill_weights)
            .selectinload(TaskSkillWeight.skill),
            selectinload(Session.completions).selectinload(TaskCompletion.athlete)
        )
    )

    updated_session = result.scalars().unique().one_or_none()

    if not updated_session:
        return None

    return updated_session


async def save_task_completions(user_id: int, session_id: int, payload: SessionCompletionPayload, db: AsyncSession) -> \
        List[TaskCompletion]:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
        .options(selectinload(Session.course))
    )
    session = result.scalars().one_or_none()
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    session.total_session_time_seconds = payload.totalSessionTime

    athlete_uuids = [c.athlete_uuid for c in payload.completions]
    athletes_q = await db.execute(select(Athlete).where(Athlete.uuid.in_(athlete_uuids), Athlete.user_id == user_id))
    athletes_map = {str(a.uuid): a.id for a in athletes_q.scalars().all()}

    if len(athletes_map) != len(set(athlete_uuids)):
        raise HTTPException(status_code=400, detail="One or more athletes not found or do not belong to you.")

    db_completions = []
    for completion_data in payload.completions:
        athlete_id = athletes_map.get(str(completion_data.athlete_uuid))
        if athlete_id:
            db_completion = TaskCompletion(
                session_id=session_id,
                athlete_id=athlete_id,
                task_id=completion_data.task_id,
                final_score=completion_data.score,
                scores_breakdown=completion_data.scores,
                notes=completion_data.notes,
                time_seconds=completion_data.time
            )
            db_completions.append(db_completion)

    db.add_all(db_completions)
    await db.commit()
    return db_completions


async def get_session_report_data(user_id: int, session_id: int, db: AsyncSession) -> Optional[dict]:
    query = (
        select(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
        .options(
            selectinload(Session.course),
            selectinload(Session.tasks).selectinload(SessionTask.task).selectinload(Task.skill_weights).selectinload(
                TaskSkillWeight.skill),
            selectinload(Session.completions).options(
                selectinload(TaskCompletion.athlete).selectinload(Athlete.positions),
                selectinload(TaskCompletion.task)
            )
        )
    )
    result = await db.execute(query)
    session = result.scalars().unique().one_or_none()

    if not session:
        return None

    evaluations = {}
    participating_athlete_objects = {}
    for completion in session.completions:
        if not completion.athlete:
            continue

        eval_key = f"{completion.athlete.uuid}-{completion.task_id}"
        evaluations[eval_key] = {
            "scores": completion.scores_breakdown or {},
            "notes": completion.notes,
            "time": completion.time_seconds,
        }
        if completion.athlete.uuid not in participating_athlete_objects:
            participating_athlete_objects[completion.athlete.uuid] = completion.athlete

    report_data = {
        "course": session.course,
        "session": session,
        "participatingAthletes": list(participating_athlete_objects.values()),
        "evaluations": evaluations,
        "totalSessionTime": session.total_session_time_seconds or 0,
    }

    return report_data


async def upload_course_image(user_id: int, course_id: int, file: UploadFile, db: AsyncSession) -> str:
    db_course = await get_course_details(user_id, course_id, db)
    if not db_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found or you do not have permission."
        )

    try:
        if db_course.cover_image_url:
            await image_upload_service.delete_image(db_course.cover_image_url)

        upload_result = await image_upload_service.upload_image(
            file=file,
            image_type=ImageType.COURSE,
            user_id=user_id,
            entity_id=course_id
        )

        db_course.cover_image_url = upload_result.url
        await db.commit()
        await db.refresh(db_course)

        return upload_result.url

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload course image: {str(e)}"
        )


async def get_all_events(user_id: int, db: AsyncSession) -> List[EventItem]:
    query = (
        select(Session)
        .options(selectinload(Session.course))
        .where(Session.user_id == user_id, Session.is_template == False)
        .order_by(Session.scheduled_date.desc())
    )
    result = await db.execute(query)
    sessions = result.scalars().unique().all()

    event_list = []
    for s in sessions:
        event_list.append(EventItem(
            id=s.id,
            title=s.name,
            date=s.scheduled_date,
            is_complete=s.status == 'Complete',
            type="course" if s.course_id else "quick_session",
            course_id=s.course_id,
            course_name=s.course.name if s.course else None
        ))

    return event_list
