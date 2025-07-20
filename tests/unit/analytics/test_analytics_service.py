# tests/unit/analytics/test_analytics_service.py

from datetime import date, datetime, timedelta, UTC
from unittest.mock import patch, AsyncMock, MagicMock, call
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.analytics import constants
from src.analytics.schemas import AthleteSkillProgression, SkillScore, AthleteCreationStat
from src.analytics.service import (
    get_athlete_skill_progression,
    calculate_ema_skill_scores,
    update_athlete_skill_scores,
    get_athlete_stats,
)
from src.analytics.utils import format_trend_data, calculate_weekly_insights
from src.athlete.models import Athlete, AthleteSkill
from src.course.models import Skill, Task, TaskCompletion, TaskSkillWeight


@pytest.fixture
def mock_db_session():
    """Provides a mocked async session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


# --- Test ID: UTC-45 ---
class TestFormatTrendDataUtil:
    """Test the format_trend_data utility function."""

    @patch('src.analytics.utils.date')
    def test_format_with_data(self, mock_date):
        """UTC-45-TC-01: Success: Format a dictionary with some data."""
        # Prerequisite
        fixed_today = date(2025, 7, 17)
        mock_date.today.return_value = fixed_today
        six_days_ago = fixed_today - timedelta(days=6)  # July 11

        # Input
        daily_counts_dict = {
            fixed_today: 5,
            six_days_ago: 10,
        }

        # Execute
        result = format_trend_data(daily_counts_dict)

        # Expected Output
        assert len(result) == 7
        assert result[0]['date'] == six_days_ago.isoformat()
        assert result[0]['count'] == 10
        assert result[0]['day_name'] == 'Fri'
        assert result[6]['date'] == fixed_today.isoformat()
        assert result[6]['count'] == 5
        assert result[6]['day_name'] == 'Thu'
        assert result[1]['count'] == 0  # A day with no data

    @patch('src.analytics.utils.date')
    def test_format_empty_dict(self, mock_date):
        """UTC-45-TC-02: Success: Format an empty dictionary."""
        # Prerequisite
        mock_date.today.return_value = date(2025, 7, 17)

        # Input
        daily_counts_dict = {}

        # Execute
        result = format_trend_data(daily_counts_dict)

        # Expected Output
        assert len(result) == 7
        assert all(item['count'] == 0 for item in result)


# --- Test ID: UTC-46 ---
class TestCalculateWeeklyInsightsUtil:
    """Test the calculate_weekly_insights utility function."""

    def test_positive_growth(self):
        """UTC-46-TC-01: Success: Positive growth week-over-week."""
        trend = [{"count": 2, "day_name": "Mon"}, {"count": 8, "day_name": "Tue"}]
        week_change, peak_day, avg_daily, is_growing = calculate_weekly_insights(
            10, 5, trend
        )
        assert week_change == 100.0
        assert is_growing is True
        assert peak_day == "Tue"
        assert avg_daily == 1.4

    def test_negative_growth(self):
        """UTC-46-TC-02: Success: Negative growth week-over-week."""
        trend = [{"count": 2, "day_name": "Mon"}]
        week_change, _, _, is_growing = calculate_weekly_insights(5, 10, trend)
        assert week_change == -50.0
        assert is_growing is False

    def test_growth_from_zero(self):
        """UTC-46-TC-03: Success: Growth from a zero-count previous week."""
        trend = [{"count": 7, "day_name": "Mon"}]
        week_change, _, avg_daily, is_growing = calculate_weekly_insights(7, 0, trend)
        assert week_change == 100.0
        assert is_growing is True
        assert avg_daily == 1.0

    def test_no_previous_data(self):
        """UTC-46-TC-04: Edge Case: No previous week data."""
        trend = [{"count": 10, "day_name": "Mon"}]
        week_change, _, _, is_growing = calculate_weekly_insights(10, None, trend)
        assert week_change is None
        assert is_growing is None

    def test_no_current_week_activity(self):
        """UTC-46-TC-05: Edge Case: No activity in the current week."""
        trend = [{"count": 0, "day_name": "Mon"}, {"count": 0, "day_name": "Tue"}]
        week_change, peak_day, avg_daily, is_growing = calculate_weekly_insights(0, 5, trend)
        assert week_change == -100.0
        assert is_growing is False
        assert peak_day is None
        assert avg_daily == 0.0


# --- Test ID: UTC-47 ---
@pytest.mark.asyncio
class TestGetAthleteSkillProgression:
    """Tests the get_athlete_skill_progression service function."""

    async def test_get_progression_success(self, mock_db_session):
        """UTC-47-TC-01: Success: Calculate progression for an athlete with activity."""
        user_id = 1
        athlete_uuid = uuid4()
        athlete_id = 100

        # Mocks
        mock_athlete = MagicMock(spec=Athlete)
        mock_athlete.id = athlete_id
        mock_athlete.uuid = athlete_uuid
        mock_athlete.user_id = user_id
        mock_athlete.skill_levels = [
            MagicMock(spec=AthleteSkill, skill_id=1, current_score=85.5),
            MagicMock(spec=AthleteSkill, skill_id=2, current_score=70.0),
        ]

        mock_user_skills = [
            MagicMock(spec=Skill, id=1, name="Shooting"),
            MagicMock(spec=Skill, id=2, name="Dribbling"),
            MagicMock(spec=Skill, id=3, name="Passing"),
        ]

        completion_dates = [date(2025, 7, 10), date(2025, 7, 15)]

        mock_day_one_task = MagicMock(spec=Task)
        mock_day_one_task.skill_weights = [
            MagicMock(spec=TaskSkillWeight, skill_id=1, weight=0.6),
            MagicMock(spec=TaskSkillWeight, skill_id=2, weight=0.4),
        ]
        day_one_completions = [
            MagicMock(
                spec=TaskCompletion,
                task=mock_day_one_task,
                scores_breakdown={"1": 80, "2": 70}  # score for skill_id 1 is 80, etc
            )
        ]

        # Mocking the chain of sqlalchemy calls
        mock_athlete_result = MagicMock()
        mock_athlete_result.scalar_one_or_none.return_value = mock_athlete
        mock_skills_result = MagicMock()
        mock_skills_result.scalars.return_value.all.return_value = mock_user_skills
        mock_dates_result = MagicMock()
        mock_dates_result.scalars.return_value.all.return_value = completion_dates
        mock_completions_result = MagicMock()
        mock_completions_result.scalars.return_value.unique.return_value.all.return_value = day_one_completions

        mock_db_session.execute.side_effect = [
            mock_athlete_result,
            mock_skills_result,
            mock_dates_result,
            mock_completions_result,
        ]

        # Execute
        progression = await get_athlete_skill_progression(user_id, athlete_uuid, mock_db_session)

        # Expected weighted average for day one:
        # (This calculation is now handled inside the service function)
        # The expected values are based on the logic in the *fixed* service.py
        expected_day_one = [
            SkillScore(skill_id=1, skill_name="Shooting", average_score=80.0),
            SkillScore(skill_id=2, skill_name="Dribbling", average_score=70.0),
            SkillScore(skill_id=3, skill_name="Passing", average_score=0.0),
        ]
        expected_current = [
            SkillScore(skill_id=1, skill_name="Shooting", average_score=85.5),
            SkillScore(skill_id=2, skill_name="Dribbling", average_score=70.0),
            SkillScore(skill_id=3, skill_name="Passing", average_score=0.0),
        ]

        assert isinstance(progression, AthleteSkillProgression)
        assert progression.day_one == expected_day_one
        assert progression.current == expected_current

    async def test_athlete_not_found(self, mock_db_session):
        """UTC-47-TC-02: Failure: Athlete not found."""
        mock_athlete_result = MagicMock()
        mock_athlete_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_athlete_result

        with pytest.raises(HTTPException) as exc_info:
            await get_athlete_skill_progression(1, uuid4(), mock_db_session)

        assert exc_info.value.status_code == 404
        # A more precise check for the error detail from the service file
        assert "Athlete not found" in exc_info.value.detail

    async def test_no_user_skills(self, mock_db_session):
        """UTC-47-TC-03: Edge Case: User has no skills defined."""
        mock_athlete = MagicMock(spec=Athlete)
        mock_athlete_result = MagicMock()
        mock_athlete_result.scalar_one_or_none.return_value = mock_athlete
        mock_skills_result = MagicMock()
        mock_skills_result.scalars.return_value.all.return_value = []  # No skills
        mock_db_session.execute.side_effect = [mock_athlete_result, mock_skills_result]

        result = await get_athlete_skill_progression(1, uuid4(), mock_db_session)

        assert result == AthleteSkillProgression(day_one=[], current=[])

    async def test_no_task_completions(self, mock_db_session):
        """UTC-47-TC-04: Edge Case: Athlete has no task completions."""
        # Mocks
        mock_athlete = MagicMock(spec=Athlete, id=100)
        mock_athlete.skill_levels = [MagicMock(spec=AthleteSkill, skill_id=1, current_score=50.0)]
        mock_user_skills = [MagicMock(spec=Skill, id=1, name="Passing")]

        mock_athlete_result = MagicMock()
        mock_athlete_result.scalar_one_or_none.return_value = mock_athlete
        mock_skills_result = MagicMock()
        mock_skills_result.scalars.return_value.all.return_value = mock_user_skills
        mock_dates_result = MagicMock()
        mock_dates_result.scalars.return_value.all.return_value = []  # No completions

        mock_db_session.execute.side_effect = [
            mock_athlete_result, mock_skills_result, mock_dates_result
        ]

        progression = await get_athlete_skill_progression(1, uuid4(), mock_db_session)

        assert progression.day_one == [SkillScore(skill_id=1, skill_name="Passing", average_score=0.0)]
        assert progression.current == [SkillScore(skill_id=1, skill_name="Passing", average_score=50.0)]


# --- Test ID: UTC-48 ---
@pytest.mark.asyncio
class TestCalculateEmaSkillScores:
    """Tests the calculate_ema_skill_scores service function."""

    def _create_mock_completion(self, session_id, dt, scores, weights):
        mock_task = MagicMock(spec=Task)
        mock_task.skill_weights = [
            MagicMock(spec=TaskSkillWeight, skill_id=skill_id, weight=weight)
            for skill_id, weight in weights.items()
        ]
        return MagicMock(
            spec=TaskCompletion,
            session_id=session_id,
            completed_at=dt,
            scores_breakdown={str(k): v for k, v in scores.items()},
            task=mock_task
        )

    async def test_calculate_ema_success(self, mock_db_session):
        """UTC-48-TC-01: Success: Calculate EMA across multiple sessions."""
        # Prerequisite: Mock completions
        completions = [
            # Session 1: Initializes the EMA
            self._create_mock_completion(1, datetime(2025, 1, 1, tzinfo=UTC), {10: 80}, {10: 1.0}),
            # Session 2: Updates the EMA
            self._create_mock_completion(2, datetime(2025, 1, 2, tzinfo=UTC), {10: 90}, {10: 1.0}),
            # Session 3: Updates again
            self._create_mock_completion(3, datetime(2025, 1, 3, tzinfo=UTC), {10: 100}, {10: 1.0}),
        ]

        # This setup needs to be compatible with the new session-based logic in service.py
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = completions
        mock_db_session.execute.return_value = mock_result

        # Execute
        scores = await calculate_ema_skill_scores(mock_db_session, 1)

        # The expected score from the service's fixed logic is 88.1
        assert scores == {10: 88.1}

    async def test_calculate_with_exclude_session(self, mock_db_session):
        """UTC-48-TC-02: Success: Exclude a specific session from calculation."""
        completions = [
            self._create_mock_completion(1, datetime(2025, 1, 1, tzinfo=UTC), {10: 80}, {10: 1.0}),
            self._create_mock_completion(2, datetime(2025, 1, 2, tzinfo=UTC), {10: 500}, {10: 1.0}),  # Excluded
            self._create_mock_completion(3, datetime(2025, 1, 3, tzinfo=UTC), {10: 100}, {10: 1.0}),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = completions
        mock_db_session.execute.return_value = mock_result

        # Execute
        scores = await calculate_ema_skill_scores(mock_db_session, 1, exclude_session_id=2)

        # The expected score from the service's fixed logic is 86.0
        assert scores == {10: 86.0}

    async def test_no_completions(self, mock_db_session):
        """UTC-48-TC-03: Edge Case: No task completions for the athlete."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        scores = await calculate_ema_skill_scores(mock_db_session, 1)

        assert scores == {}


# --- Test ID: UTC-49 ---
@pytest.mark.asyncio
@patch("src.analytics.service.calculate_ema_skill_scores", new_callable=AsyncMock)
class TestUpdateAthleteSkillScores:
    """Tests the update_athlete_skill_scores service function."""

    async def test_update_scores_success(self, mock_calculate_ema, mock_db_session):
        """UTC-49-TC-01: Success: Calculate and upsert new scores."""
        # Prerequisite
        athlete_id = 1
        mock_scores = {1: 95.5, 2: 88.12}
        mock_calculate_ema.return_value = mock_scores

        # Execute
        await update_athlete_skill_scores(athlete_id, mock_db_session)

        # Expected
        mock_calculate_ema.assert_awaited_once_with(mock_db_session, athlete_id)

        # Check that execute was called with an upsert statement
        mock_db_session.execute.assert_awaited_once()
        # A more detailed check on the statement itself
        executed_stmt = mock_db_session.execute.call_args[0][0]
        assert isinstance(executed_stmt, type(pg_insert(AthleteSkill)))
        assert executed_stmt.is_insert

    async def test_no_scores_to_update(self, mock_calculate_ema, mock_db_session):
        """UTC-49-TC-02: Edge Case: No scores are calculated."""
        # Prerequisite
        mock_calculate_ema.return_value = {}

        # Execute
        await update_athlete_skill_scores(1, mock_db_session)

        # Expected
        mock_db_session.execute.assert_not_awaited()