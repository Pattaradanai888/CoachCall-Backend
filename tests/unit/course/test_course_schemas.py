# tests/unit/course/test_schemas.py

from datetime import date, datetime, timezone
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError, model_validator

from src.course.schemas import (
    CourseCreate, SessionRead, SessionReportData, TaskSkillWeightCreate, FinalEvaluationData
)


# --- Test ID: UTC-35 ---
class TestCourseSchemas:
    """Tests for Pydantic schema validation, aliases, and computed fields."""

    def test_course_create_handles_title_alias(self):
        """UTC-35-TC-01: Success: CourseCreate correctly handles the 'title' alias."""
        course_data = {
            "title": "My Awesome Course",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "sessions": []
        }
        course = CourseCreate.model_validate(course_data)
        assert course.name == "My Awesome Course"
        # Check that dumping also works with the alias
        assert course.model_dump(by_alias=True)["title"] == "My Awesome Course"

    def test_session_read_computes_task_count(self):
        """UTC-35-TC-02: Success: SessionRead correctly calculates task_count."""
        # FIX: The nested mocks need to have their own attributes defined to satisfy Pydantic's validation.
        # We need to mock the structure that SessionRead expects: Session -> SessionTask -> Task
        mock_tasks = []
        for i in range(3):
            # Mock the innermost Task object
            mock_task_orm = MagicMock()
            mock_task_orm.id = i
            mock_task_orm.name = f"Task {i}"
            mock_task_orm.description = "A description"
            mock_task_orm.duration_minutes = 10
            mock_task_orm.skill_weights = [] # Must be an iterable

            # Mock the SessionTask link table object
            mock_session_task_orm = MagicMock()
            mock_session_task_orm.sequence = i + 1
            mock_session_task_orm.task = mock_task_orm # Link the task here
            mock_tasks.append(mock_session_task_orm)

        # Mocking the top-level ORM-like object that SessionRead would be created from
        mock_session_orm = MagicMock()
        mock_session_orm.id = 1
        mock_session_orm.name = "Test Session"
        mock_session_orm.description = "A test session"
        mock_session_orm.scheduled_date = datetime.now(timezone.utc)
        mock_session_orm.is_template = False
        mock_session_orm.status = "To Do"
        mock_session_orm.total_duration_minutes = 60
        mock_session_orm.completions = []
        # The key attribute for this test
        mock_session_orm.tasks = mock_tasks # Use the fully defined mock tasks

        # This should now pass validation because all nested fields exist
        session_read = SessionRead.from_orm(mock_session_orm)

        assert session_read.task_count == 3

    def test_session_report_data_populates_by_name(self):
        """UTC-35-TC-03: Success: SessionReportData populates correctly by name."""
        # This tests that `populate_by_name=True` works for aliased fields
        report_data_dict = {
            "session": {
                "id": 1,
                "name": "Report Session",
                "description": None,  # FIX: Add the optional 'description' field, even if it's None.
                "scheduled_date": "2024-08-01T10:00:00Z",
                "is_template": False,
                "status": "Complete",
                "tasks": [],
                "total_duration_minutes": 0,
            },
            "participatingAthletes": [
                {
                    "uuid": uuid.uuid4(),
                    "name": "Athlete One",
                    "profile_image_url": None,
                    "positions": []
                }
            ],
            "evaluations": {
                "some-key": {
                    "scores": {"1": 95.5},
                    "notes": "Good work",
                    "time": 300
                }
            },
            "skillComparisonData": {
                "athlete1-uuid": {
                    "before": [
                        {"skill_id": 1, "skill_name": "Passing", "average_score": 80.0}
                    ],
                    "after": [
                        {"skill_id": 1, "skill_name": "Passing", "average_score": 85.0}
                    ]
                }
            },
            "totalSessionTime": 3600
        }

        report_data = SessionReportData.model_validate(report_data_dict)

        assert report_data.total_session_time == 3600
        assert len(report_data.participating_athletes) == 1
        assert report_data.participating_athletes[0].name == "Athlete One"

    def test_task_skill_weight_validation(self):
        """UTC-35-TC-04: Failure: TaskSkillWeightCreate validation fails for out-of-range weight."""
        # Test weight greater than 1
        with pytest.raises(ValidationError) as exc_info_gt:
            TaskSkillWeightCreate(skill_id=1, weight=1.5)
        assert "Input should be less than or equal to 1" in str(exc_info_gt.value)

        # Test weight less than 0
        with pytest.raises(ValidationError) as exc_info_lt:
            TaskSkillWeightCreate(skill_id=1, weight=-0.5)
        assert "Input should be greater than 0" in str(exc_info_lt.value)

        # Test valid weight
        try:
            TaskSkillWeightCreate(skill_id=1, weight=0.75)
        except ValidationError:
            pytest.fail("TaskSkillWeightCreate raised ValidationError unexpectedly for a valid weight.")