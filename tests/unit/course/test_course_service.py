# tests/unit/course/test_service.py

import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status

from src.athlete.models import Athlete
from src.course.models import Skill, Session, Course, TaskCompletion
from src.course.schemas import SkillCreate, SessionCreate, CourseCreate, CourseArchiveStatusUpdate, \
    SessionCompletionPayload
from src.course.service import (
    create_skill, get_skills, create_session, update_session, delete_session, create_course,
    update_course, delete_course, update_course_archive_status, update_course_attendees,
    save_task_completions, get_session_report_data, upload_course_image, get_all_events
)
from src.upload.schemas import UploadResponse, ImageType


@pytest.fixture
def mock_db_session():
    """Provides a mocked async session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.flush = AsyncMock()
    return session


# --- Test ID: UTC-22 ---
@pytest.mark.asyncio
class TestSkillService:
    async def test_create_skill_success(self, mock_db_session):
        """UTC-22-TC-01: Success: Create a new skill."""
        user_id = 1
        skill_data = SkillCreate(name="Dribbling", description="Handling the ball.")

        async def refresh_side_effect(obj):
            obj.id = 101

        mock_db_session.refresh.side_effect = refresh_side_effect

        new_skill = await create_skill(user_id, skill_data, mock_db_session)

        mock_db_session.add.assert_called_once()
        added_obj = mock_db_session.add.call_args[0][0]
        assert isinstance(added_obj, Skill)
        assert added_obj.name == "Dribbling"
        assert added_obj.user_id == user_id
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()
        assert new_skill.id == 101

    async def test_get_skills_for_user(self, mock_db_session):
        """UTC-22-TC-02: Success: Get all skills for a user."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [Skill(id=1), Skill(id=2)]
        mock_db_session.execute.return_value = mock_result
        skills = await get_skills(1, mock_db_session)
        assert len(skills) == 2

    async def test_get_skills_empty(self, mock_db_session):
        """UTC-22-TC-03: Success: No skills exist for a user."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        skills = await get_skills(1, mock_db_session)
        assert skills == []


# --- Test ID: UTC-23, UTC-24, UTC-25 ---
@pytest.mark.asyncio
class TestSessionService:
    @pytest.fixture
    def session_create_payload(self):
        return SessionCreate(
            name="Test Session",
            scheduled_date=datetime.now(timezone.utc),
            tasks=[{
                "name": "Task 1",
                "duration_minutes": 15,
                "skill_weights": [{"skill_id": 1, "weight": 0.5}]
            }]
        )

    async def test_create_session_success(self, mock_db_session, session_create_payload):
        """UTC-23-TC-01: Success: Create a session with tasks and valid skill weights."""
        mock_valid_skills = MagicMock()
        mock_valid_skills.scalars.return_value.all.return_value = [Skill(id=1)]
        mock_final_session = MagicMock()
        mock_final_session.scalars.return_value.unique.return_value.one.return_value = Session(id=1)
        mock_db_session.execute.side_effect = [mock_valid_skills, mock_final_session]

        created_session = await create_session(1, session_create_payload, mock_db_session)

        assert isinstance(created_session, Session)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_create_session_invalid_skill_id(self, mock_db_session, session_create_payload):
        """UTC-23-TC-02: Failure: Attempt to create a session with an invalid skill_id."""
        mock_invalid_skills = MagicMock()
        mock_invalid_skills.scalars.return_value.all.return_value = []  # Empty list means skill_id was not found
        mock_db_session.execute.return_value = mock_invalid_skills

        with pytest.raises(HTTPException) as exc_info:
            await create_session(1, session_create_payload, mock_db_session)
        assert exc_info.value.status_code == 400
        assert "One or more skill IDs are invalid" in exc_info.value.detail
        mock_db_session.commit.assert_not_awaited()

    async def test_update_session_success(self, mock_db_session, session_create_payload):
        """UTC-24-TC-01: Success: Update a session's name and replace its tasks."""
        mock_existing_session = Session(id=1, name="Old Name", tasks=[])
        mock_initial_fetch_result = MagicMock()
        mock_initial_fetch_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_existing_session
        mock_final_fetch_result = MagicMock()
        mock_final_fetch_result.scalars.return_value.unique.return_value.one.return_value = mock_existing_session

        mock_db_session.execute.side_effect = [mock_initial_fetch_result, mock_final_fetch_result]

        session_create_payload.name = "New Name"

        updated_session = await update_session(1, 1, session_create_payload, mock_db_session)

        assert updated_session.name == "New Name"
        mock_db_session.flush.assert_awaited_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_update_session_not_found(self, mock_db_session, session_create_payload):
        """UTC-24-TC-02: Failure: Attempt to update a session that does not exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await update_session(1, 99, session_create_payload, mock_db_session)
        assert exc_info.value.status_code == 404
        assert "Session not found" in exc_info.value.detail

    async def test_delete_session_success(self, mock_db_session):
        """UTC-25-TC-01: Success: Delete an existing session."""
        mock_session = Session(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one_or_none.return_value = mock_session
        mock_db_session.execute.return_value = mock_result

        await delete_session(1, 1, mock_db_session)

        mock_db_session.delete.assert_called_once_with(mock_session)
        mock_db_session.commit.assert_awaited_once()

    async def test_delete_session_not_found(self, mock_db_session):
        """UTC-25-TC-02: Failure: Attempt to delete a session that does not exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_session(1, 99, mock_db_session)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Session not found or you do not have permission." in exc_info.value.detail


# --- Test ID: UTC-26, UTC-27, UTC-28, UTC-29, UTC-30 ---
@pytest.mark.asyncio
class TestCourseService:
    @pytest.fixture
    def course_create_payload(self):
        athlete_uuid = uuid.uuid4()
        return CourseCreate(
            title="Pre-Season Camp",
            start_date=date(2024, 8, 1),
            end_date=date(2024, 8, 10),
            attendee_ids=[athlete_uuid],
            sessions=[{
                "name": "Day 1",
                "scheduled_date": datetime(2024, 8, 1, 9, 0, tzinfo=timezone.utc),
                "tasks": [{"name": "Warmup", "duration_minutes": 20, "skill_weights": []}]
            }]
        )

    async def test_create_course_success(self, mock_db_session, course_create_payload):
        """UTC-26-TC-01: Success: Create a course with valid sessions and attendees."""
        mock_athletes = MagicMock()
        mock_athletes.scalars.return_value.all.return_value = [Athlete(uuid=course_create_payload.attendee_ids[0])]
        mock_final_course = MagicMock()
        mock_final_course.scalars.return_value.unique.return_value.one.return_value = Course(id=1)
        mock_db_session.execute.side_effect = [mock_athletes, mock_final_course]

        new_course = await create_course(1, course_create_payload, mock_db_session)

        assert isinstance(new_course, Course)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_create_course_invalid_athlete(self, mock_db_session, course_create_payload):
        """UTC-26-TC-03: Failure: Attempt to create a course with an invalid attendee_id."""
        mock_athletes = MagicMock()
        mock_athletes.scalars.return_value.all.return_value = []  # No athletes found
        mock_db_session.execute.return_value = mock_athletes

        with pytest.raises(HTTPException) as exc_info:
            await create_course(1, course_create_payload, mock_db_session)
        assert exc_info.value.status_code == 400
        assert "One or more athlete IDs are invalid" in exc_info.value.detail

    @patch("src.course.service.get_course_details", new_callable=AsyncMock)
    async def test_update_course_success(self, mock_get_details, mock_db_session, course_create_payload):
        """UTC-27-TC-01: Success: Update an entire course structure."""
        mock_course = Course(id=1, name="Old Course Name", user_id=1, sessions=[], attendees=[])

        mock_get_details.side_effect = [mock_course, mock_course]

        mock_athlete_result = MagicMock()
        mock_athlete_result.scalars.return_value.all.return_value = [
            Athlete(uuid=course_create_payload.attendee_ids[0])
        ]
        mock_db_session.execute.return_value = mock_athlete_result

        updated_course = await update_course(1, 1, course_create_payload, mock_db_session)

        assert updated_course.name == "Pre-Season Camp"
        mock_db_session.commit.assert_awaited_once()

    @patch("src.course.service.get_course_details", new_callable=AsyncMock)
    async def test_update_course_not_found(self, mock_get_details, mock_db_session, course_create_payload):
        """UTC-27-TC-02: Failure: Attempt to update a course that does not exist."""
        mock_get_details.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await update_course(1, 99, course_create_payload, mock_db_session)
        assert exc_info.value.status_code == 404

    async def test_delete_course_success(self, mock_db_session):
        """UTC-28-TC-01: Success: Delete an existing course."""
        mock_course = Course(id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.one_or_none.return_value = mock_course
        mock_db_session.execute.return_value = mock_result

        result = await delete_course(1, 1, mock_db_session)

        assert result["deleted_course_id"] == 1
        mock_db_session.delete.assert_called_once_with(mock_course)
        mock_db_session.commit.assert_awaited_once()

    @patch("src.course.service.get_course_details", new_callable=AsyncMock)
    async def test_update_course_archive_status_success(self, mock_get_details, mock_db_session):
        """UTC-29-TC-01: Success: Archive an existing course."""
        mock_update_result = MagicMock()
        mock_update_result.rowcount = 1
        mock_db_session.execute.return_value = mock_update_result

        mock_updated_course = Course(id=1, is_archived=True)
        mock_get_details.return_value = mock_updated_course

        status_update = CourseArchiveStatusUpdate(is_archived=True)
        result = await update_course_archive_status(1, 1, status_update, mock_db_session)

        assert result.is_archived is True
        mock_db_session.commit.assert_awaited_once()

    @patch("src.course.service.get_course_details", new_callable=AsyncMock)
    async def test_update_course_attendees_success(self, mock_get_details, mock_db_session):
        """UTC-30-TC-01: Success: Replace the list of course attendees."""
        new_athlete_uuid = uuid.uuid4()
        mock_course = Course(id=1, attendees=[])
        mock_get_details.return_value = mock_course
        mock_athlete_result = MagicMock()
        mock_athlete_result.scalars.return_value.all.return_value = [Athlete(uuid=new_athlete_uuid)]
        mock_db_session.execute.return_value = mock_athlete_result

        await update_course_attendees(1, 1, [new_athlete_uuid], mock_db_session)

        assert len(mock_course.attendees) == 1
        assert mock_course.attendees[0].uuid == new_athlete_uuid
        mock_db_session.commit.assert_awaited_once()


# --- Test ID: UTC-31 & UTC-32 ---
@pytest.mark.asyncio
class TestCompletionAndReportService:
    async def test_save_task_completions_success(self, mock_db_session):
        """UTC-31-TC-01: Success: Save valid completion data for a session."""
        payload = SessionCompletionPayload(
            completions=[{"athlete_uuid": uuid.uuid4(), "task_id": 1, "score": 90, "scores": {}, "time": 100}],
            totalSessionTime=1200
        )
        mock_session = Session(id=1, user_id=1)
        mock_athlete_map = {str(payload.completions[0].athlete_uuid): 5}

        mock_session_result = MagicMock()
        mock_session_result.scalars.return_value.one_or_none.return_value = mock_session

        mock_athlete_result = MagicMock()
        mock_athlete_result.scalars.return_value.all.return_value = [
            Athlete(id=5, uuid=payload.completions[0].athlete_uuid)]

        mock_db_session.execute.side_effect = [mock_session_result, mock_athlete_result]

        await save_task_completions(1, 1, payload, mock_db_session)

        assert mock_session.total_session_time_seconds == 1200
        mock_db_session.add_all.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_get_session_report_data_success(self, mock_db_session):
        """UTC-32-TC-01: Success: Get report data for a completed session."""
        mock_athlete = MagicMock()
        mock_athlete.uuid = uuid.uuid4()

        mock_completion = MagicMock(spec=TaskCompletion)
        mock_completion.athlete = mock_athlete
        mock_completion.task_id = 10
        mock_completion.scores_breakdown = {"metric": 1}
        mock_completion.notes = "Notes"
        mock_completion.time_seconds = 120

        mock_session = MagicMock(spec=Session)
        mock_session.completions = [mock_completion]
        mock_session.course = Course(id=1, name="Test Course")
        mock_session.total_session_time_seconds = 1800

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_session
        mock_db_session.execute.return_value = mock_result

        report_data = await get_session_report_data(1, 1, mock_db_session)

        assert report_data is not None
        assert len(report_data["participatingAthletes"]) == 1
        eval_key = f"{mock_athlete.uuid}-10"
        assert eval_key in report_data["evaluations"]
        assert report_data["evaluations"][eval_key]["notes"] == "Notes"


# --- Test ID: UTC-33 ---
@pytest.mark.asyncio
@patch("src.course.service.image_upload_service", new_callable=AsyncMock)
@patch("src.course.service.get_course_details", new_callable=AsyncMock)
class TestCourseImageService:
    async def test_upload_image_first_time_success(self, mock_get_details, mock_image_service, mock_db_session):
        """UTC-33-TC-01: Success (Upload): Upload an image for a course for the first time."""
        mock_course = Course(id=1, cover_image_url=None)
        mock_get_details.return_value = mock_course
        mock_image_service.upload_image.return_value = UploadResponse(url="http://new.url/img.png")

        result_url = await upload_course_image(1, 1, MagicMock(), mock_db_session)

        assert result_url == "http://new.url/img.png"
        mock_image_service.delete_image.assert_not_called()
        assert mock_course.cover_image_url == "http://new.url/img.png"
        mock_db_session.commit.assert_awaited_once()

    async def test_upload_replace_image_success(self, mock_get_details, mock_image_service, mock_db_session):
        """UTC-33-TC-02: Success (Upload): Replace an existing course image."""
        mock_course = Course(id=1, cover_image_url="old_url")
        mock_get_details.return_value = mock_course
        mock_image_service.upload_image.return_value = UploadResponse(url="new_url")

        await upload_course_image(1, 1, MagicMock(), mock_db_session)

        mock_image_service.delete_image.assert_awaited_once_with("old_url")
        mock_image_service.upload_image.assert_awaited_once()

    async def test_upload_image_service_failure(self, mock_get_details, mock_image_service, mock_db_session):
        """UTC-33-TC-03: Failure (Upload): The external image service fails during upload."""
        mock_get_details.return_value = Course(id=1)
        mock_image_service.upload_image.side_effect = Exception("Upload failed")

        with pytest.raises(HTTPException) as exc_info:
            await upload_course_image(1, 1, MagicMock(), mock_db_session)

        assert exc_info.value.status_code == 500
        mock_db_session.rollback.assert_awaited_once()


# --- Test ID: UTC-34 ---
@pytest.mark.asyncio
class TestEventService:
    async def test_get_all_events_success(self, mock_db_session):
        """UTC-34-TC-01: Get a list of events from various session types."""
        mock_course = Course(id=1, name="Summer Camp")
        mock_sessions = [
            Session(id=1, name="Day 1", scheduled_date=datetime.now(), status="Complete", course_id=1,
                    course=mock_course),
            Session(id=2, name="Quick Drill", scheduled_date=datetime.now(), status="To Do", course_id=None,
                    course=None)
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = mock_sessions
        mock_db_session.execute.return_value = mock_result

        events = await get_all_events(1, mock_db_session)

        assert len(events) == 2

        course_event = next(e for e in events if e.id == 1)
        assert course_event.type == "course"
        assert course_event.is_complete is True
        assert course_event.course_name == "Summer Camp"

        quick_session_event = next(e for e in events if e.id == 2)
        assert quick_session_event.type == "quick_session"
        assert quick_session_event.is_complete is False
        assert quick_session_event.course_name is None