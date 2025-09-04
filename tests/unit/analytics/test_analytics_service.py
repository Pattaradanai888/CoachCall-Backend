# tests/unit/analytics/test_analytics_service.py

from datetime import date, datetime, timedelta, UTC
from unittest.mock import patch, AsyncMock, MagicMock, call
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.analytics import constants
from src.analytics.schemas import (
    AthleteSkillProgression,
    SkillScore,
    AthleteCreationStat,
    ActivityStats,
    EfficiencyStats,
    ComparativeStat,
    EngagementStats,
    GrowthInsight,
    TeamSkillStats,
    PlayerInsight,
    TopSkill,
    MotivationalHighlight,
    CoachStatData,
    LeaderboardResponse
)
from src.analytics.service import (
    get_athlete_skill_progression,
    calculate_ema_skill_scores,
    update_athlete_skill_scores,
    get_athlete_stats,
    _calculate_change_percent,
    _get_activity_and_efficiency_stats,
    _get_engagement_stats,
    _get_skill_and_player_insights,
    _generate_motivational_highlight,
    get_coach_dashboard_stats,
    _calculate_day_one_average_score,
    _calculate_improvement_slope,
    get_leaderboard_data

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

        # FIX: Explicitly create mocks with real attribute values, not sub-mocks
        mock_skill_1 = MagicMock(spec=Skill)
        mock_skill_1.id = 1
        mock_skill_1.name = "Shooting"
        mock_skill_2 = MagicMock(spec=Skill)
        mock_skill_2.id = 2
        mock_skill_2.name = "Dribbling"
        mock_skill_3 = MagicMock(spec=Skill)
        mock_skill_3.id = 3
        mock_skill_3.name = "Passing"
        mock_user_skills = [mock_skill_1, mock_skill_2, mock_skill_3]


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
                scores_breakdown={"1": 80, "2": 70}
            )
        ]

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

        progression = await get_athlete_skill_progression(user_id, athlete_uuid, mock_db_session)

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
        mock_athlete = MagicMock(spec=Athlete, id=100)
        mock_athlete.skill_levels = [MagicMock(spec=AthleteSkill, skill_id=1, current_score=50.0)]

        # FIX: Explicitly create mock with real attribute values
        mock_skill = MagicMock(spec=Skill)
        mock_skill.id = 1
        mock_skill.name = "Passing"
        mock_user_skills = [mock_skill]

        mock_athlete_result = MagicMock()
        mock_athlete_result.scalar_one_or_none.return_value = mock_athlete
        mock_skills_result = MagicMock()
        mock_skills_result.scalars.return_value.all.return_value = mock_user_skills
        mock_dates_result = MagicMock()
        mock_dates_result.scalars.return_value.all.return_value = []

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

# --- Test ID: UTC-51 ---
class TestCalculateChangePercentUtil:
    """UTC-51 Tests the _calculate_change_percent utility function."""

    def test_positive_change(self):
        """UTC-51-TC-01: Success: Calculate a positive percentage increase."""
        result = _calculate_change_percent(current=150, previous=100)
        assert result == 50.0

    def test_negative_change(self):
        """UTC-51-TC-02: Success: Calculate a negative percentage decrease."""
        result = _calculate_change_percent(current=75, previous=100)
        assert result == -25.0

    def test_no_change(self):
        """UTC-51-TC-03: Success: Calculate zero change."""
        result = _calculate_change_percent(current=100, previous=100)
        assert result == 0.0

    def test_growth_from_zero(self):
        """UTC-51-TC-04: Edge Case: Growth from a zero previous value."""
        result = _calculate_change_percent(current=50, previous=0)
        assert result == 100.0

    def test_no_growth_from_zero(self):
        """UTC-51-TC-05: Edge Case: No growth when both values are zero."""
        result = _calculate_change_percent(current=0, previous=0)
        assert result == 0.0

    def test_none_previous_value(self):
        """UTC-51-TC-06: Edge Case: Previous value is None."""
        result = _calculate_change_percent(current=100, previous=None)
        assert result is None


# --- Test ID: UTC-52 ---
@pytest.mark.asyncio
class TestGetActivityAndEfficiencyStats:
    """Tests the _get_activity_and_efficiency_stats service helper function."""

    @pytest.fixture
    def mock_session_row(self):
        """Helper to create a mock row from the session query result."""

        def _creator(course_id=None):
            row = MagicMock()
            row.id = 1
            row.course_id = course_id
            return row

        return _creator

    async def test_get_stats_with_data(self, mock_db_session, mock_session_row):
        """UTC-52-TC-01: Success: Calculate stats for an active coach with data."""
        # Arrange: Mock the sequence of database calls
        # 1. sessions_last_month
        # 2. courses_created_month
        # 3. courses_created_last_month
        # 4. total_sessions
        # 5. user_creation_date
        mock_db_session.scalar.side_effect = [
            5,  # sessions_last_month
            4,  # courses_created_month
            2,  # courses_created_last_month
            50,  # total_sessions
            datetime.now(UTC) - timedelta(weeks=8)  # user_creation_date
        ]

        # Mock the execute call for sessions this month
        mock_session_results = [mock_session_row(course_id=123) for _ in range(8)]  # 8 from templates
        mock_session_results.extend([mock_session_row() for _ in range(2)])  # 2 standalone
        mock_execute_result = MagicMock()
        mock_execute_result.all.return_value = mock_session_results
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        activity, efficiency = await _get_activity_and_efficiency_stats(
            user_id=1,
            month_ago=datetime.now(UTC) - timedelta(days=30),
            two_months_ago=datetime.now(UTC) - timedelta(days=60),
            db=mock_db_session
        )

        # Assert
        assert isinstance(activity, ActivityStats)
        assert isinstance(efficiency, EfficiencyStats)

        # Activity assertions
        assert activity.sessions_conducted_month == ComparativeStat(current=10, previous=5, change_percent=100.0)
        assert activity.courses_created_month == ComparativeStat(current=4, previous=2, change_percent=100.0)
        assert activity.avg_sessions_per_week == pytest.approx(6.2, 0.1)  # 50 sessions / ~8 weeks

        # Efficiency assertions
        assert efficiency.sessions_from_template_month == 8
        assert efficiency.total_sessions_month == 10
        assert efficiency.template_reuse_rate == 80.0

    async def test_get_stats_no_data(self, mock_db_session):
        """UTC-52-TC-02: Edge Case: Calculate stats for a new coach with no data."""
        # Arrange
        mock_db_session.scalar.side_effect = [0, 0, 0, 0, datetime.now(UTC)]  # All counts are zero
        mock_execute_result = MagicMock()
        mock_execute_result.all.return_value = []  # No sessions this month
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        activity, efficiency = await _get_activity_and_efficiency_stats(
            user_id=1,
            month_ago=datetime.now(UTC) - timedelta(days=30),
            two_months_ago=datetime.now(UTC) - timedelta(days=60),
            db=mock_db_session
        )

        # Assert
        assert activity.sessions_conducted_month == ComparativeStat(current=0, previous=0, change_percent=0.0)
        assert activity.courses_created_month == ComparativeStat(current=0, previous=0, change_percent=0.0)
        assert activity.avg_sessions_per_week == 0.0
        assert efficiency.template_reuse_rate == 0.0

    async def test_get_stats_no_sessions_this_month(self, mock_db_session):
        """UTC-52-TC-03: Edge Case: Data exists, but no sessions this month (tests zero division)."""
        # Arrange
        mock_db_session.scalar.side_effect = [5, 1, 1, 5, datetime.now(UTC) - timedelta(weeks=4)]
        mock_execute_result = MagicMock()
        mock_execute_result.all.return_value = []  # No sessions this month
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        activity, efficiency = await _get_activity_and_efficiency_stats(
            user_id=1,
            month_ago=datetime.now(UTC) - timedelta(days=30),
            two_months_ago=datetime.now(UTC) - timedelta(days=60),
            db=mock_db_session
        )

        # Assert: Key check is that template_reuse_rate is 0, not an error
        assert efficiency.template_reuse_rate == 0.0
        assert efficiency.sessions_from_template_month == 0
        assert efficiency.total_sessions_month == 0
        assert activity.sessions_conducted_month.current == 0
        assert activity.sessions_conducted_month.previous == 5
        assert activity.sessions_conducted_month.change_percent == -100.0


# --- Test ID: UTC-53 ---
@pytest.mark.asyncio
class TestGetEngagementStats:
    """Tests the _get_engagement_stats service helper function."""

    @pytest.fixture
    def mock_athlete_list(self):
        """Helper to create a list of mock Athlete objects."""
        return [MagicMock(spec=Athlete) for _ in range(15)]

    async def test_get_stats_accelerating_growth(self, mock_db_session, mock_athlete_list):
        """UTC-53-TC-01: Success: Calculate stats with an accelerating growth trend."""
        # Arrange
        # 1. Mock the execute call for all_athletes (Corrected chain with .scalars())
        mock_athlete_execute_result = MagicMock()
        mock_athlete_execute_result.scalars.return_value.unique.return_value.all.return_value = mock_athlete_list
        # 2. Mock the attendance query
        mock_attendance_row = MagicMock()
        mock_attendance_row.total = 20
        mock_attendance_row.present = 18
        mock_attendance_execute_result = MagicMock()
        mock_attendance_execute_result.first.return_value = mock_attendance_row

        # Correctly mock both sequential calls to db.execute
        mock_db_session.execute.side_effect = [
            mock_athlete_execute_result,
            mock_attendance_execute_result
        ]

        # Mock scalar calls for new athletes (m1=10, m2=5, m3=2 -> accelerating)
        mock_db_session.scalar.side_effect = [10, 5, 2]

        # Act
        engagement, athletes = await _get_engagement_stats(
            user_id=1,
            month_ago=datetime.now(UTC) - timedelta(days=30),
            two_months_ago=datetime.now(UTC) - timedelta(days=60),
            three_months_ago=datetime.now(UTC) - timedelta(days=90),
            db=mock_db_session
        )

        # Assert
        assert isinstance(engagement, EngagementStats)
        assert athletes == mock_athlete_list  # This will now pass
        assert engagement.active_roster_count == 15
        assert engagement.new_athletes_month.current == 10
        assert engagement.new_athletes_month.previous == 5
        assert engagement.team_attendance_rate == 90.0
        assert engagement.growth_insight.trend_type == "accelerating"

    async def test_get_stats_no_data(self, mock_db_session):
        """UTC-53-TC-02: Edge Case: Calculate stats for a coach with no athletes or data."""
        # Arrange
        mock_athlete_execute_result = MagicMock()
        mock_athlete_execute_result.scalars.return_value.unique.return_value.all.return_value = []  # No athletes
        mock_attendance_execute_result = MagicMock()
        mock_attendance_execute_result.first.return_value = None  # No attendance

        mock_db_session.execute.side_effect = [
            mock_athlete_execute_result,
            mock_attendance_execute_result
        ]
        mock_db_session.scalar.side_effect = [0, 0, 0]  # No new athletes

        # Act
        engagement, _ = await _get_engagement_stats(1, MagicMock(), MagicMock(), MagicMock(), mock_db_session)

        # Assert
        assert engagement.active_roster_count == 0
        assert engagement.new_athletes_month.current == 0
        assert engagement.team_attendance_rate is None
        assert engagement.growth_insight.trend_type == "stable"

    async def test_get_stats_slowing_growth(self, mock_db_session, mock_athlete_list):
        """UTC-53-TC-03: Logic Case: Calculate stats with a slowing growth trend."""
        # Arrange
        mock_athlete_execute_result = MagicMock()
        mock_athlete_execute_result.scalars.return_value.unique.return_value.all.return_value = mock_athlete_list
        mock_attendance_execute_result = MagicMock()  # Mock the second call, even if not used
        mock_attendance_execute_result.first.return_value = MagicMock(total=1, present=1)

        mock_db_session.execute.side_effect = [
            mock_athlete_execute_result,
            mock_attendance_execute_result
        ]

        # Mock scalar calls for new athletes (m1=2, m2=8, m3=3 -> slowing)
        mock_db_session.scalar.side_effect = [2, 8, 3]

        # Act
        engagement, _ = await _get_engagement_stats(1, MagicMock(), MagicMock(), MagicMock(), mock_db_session)

        # Assert
        assert engagement.growth_insight.trend_type == "slowing"

    async def test_get_stats_no_attendance_data(self, mock_db_session, mock_athlete_list):
        """UTC-53-TC-04: Edge Case: Coach has athletes but no attendance data."""
        # Arrange
        mock_athlete_execute_result = MagicMock()
        mock_athlete_execute_result.scalars.return_value.unique.return_value.all.return_value = mock_athlete_list
        mock_attendance_execute_result = MagicMock()
        mock_attendance_execute_result.first.return_value = MagicMock(total=0, present=None)

        mock_db_session.execute.side_effect = [
            mock_athlete_execute_result,
            mock_attendance_execute_result
        ]
        mock_db_session.scalar.side_effect = [5, 5, 5]  # Steady growth

        # Act
        engagement, _ = await _get_engagement_stats(1, MagicMock(), MagicMock(), MagicMock(), mock_db_session)

        # Assert
        assert engagement.team_attendance_rate is None


# --- Test ID: UTC-54 ---
@pytest.mark.asyncio
class TestGetSkillAndPlayerInsights:
    """Tests the _get_skill_and_player_insights service helper function."""

    @pytest.fixture
    def mock_athletes_for_insights(self):
        """
        Provides a list of mock athletes with varying skill levels for testing.
        This version explicitly sets all attributes to their correct types.
        """
        # Athlete 1: Top performer
        athlete1 = MagicMock(spec=Athlete)
        athlete1.uuid = uuid4()
        athlete1.name = "Jordan"
        athlete1.profile_image_url = "jordan.png"
        athlete1.skill_levels = [MagicMock(current_score=95.0), MagicMock(current_score=90.0)]

        # Athlete 2: Average performer
        athlete2 = MagicMock(spec=Athlete)
        athlete2.uuid = uuid4()
        athlete2.name = "Pippen"
        athlete2.profile_image_url = "pippen.png"
        athlete2.skill_levels = [MagicMock(current_score=85.0), MagicMock(current_score=88.0)]

        # Athlete 3: No skill data yet
        athlete3 = MagicMock(spec=Athlete)
        athlete3.uuid = uuid4()
        athlete3.name = "Rodman"
        athlete3.profile_image_url = "rodman.png"
        athlete3.skill_levels = []

        return [athlete1, athlete2, athlete3]

    async def test_get_insights_success(self, mock_db_session, mock_athletes_for_insights):
        """UTC-54-TC-01: Success: Calculate insights with a full set of data."""
        # Arrange: Configure mocks to be unpackable like a tuple by setting __iter__
        mock_skill_focus_row1 = MagicMock()
        mock_skill_focus_row1.name = "Dribbling"
        mock_skill_focus_row1.count = 20
        mock_skill_focus_row1.__iter__.return_value = iter([mock_skill_focus_row1.name, mock_skill_focus_row1.count])

        mock_skill_focus_row2 = MagicMock()
        mock_skill_focus_row2.name = "Shooting"
        mock_skill_focus_row2.count = 10
        mock_skill_focus_row2.__iter__.return_value = iter([mock_skill_focus_row2.name, mock_skill_focus_row2.count])

        mock_skill_focus_result = MagicMock()
        mock_skill_focus_result.all.return_value = [mock_skill_focus_row1, mock_skill_focus_row2]

        mock_absences_row = (mock_athletes_for_insights[1], 3)
        mock_absences_result = MagicMock()
        mock_absences_result.all.return_value = [mock_absences_row]

        mock_db_session.execute.side_effect = [mock_skill_focus_result, mock_absences_result]

        # Act
        team_stats, top_performers, needs_attention = await _get_skill_and_player_insights(
            user_id=1,
            month_ago=datetime.now(UTC) - timedelta(days=30),
            all_athletes=mock_athletes_for_insights,
            db=mock_db_session
        )

        # Assert
        assert isinstance(team_stats, TeamSkillStats)
        assert team_stats.athletes_improved_percent == pytest.approx(66.7)
        assert team_stats.top_trending_skill == TopSkill(name="Dribbling")
        assert len(team_stats.skill_focus_distribution) == 2
        assert team_stats.skill_focus_distribution[0].weight == pytest.approx(66.7)

        assert len(top_performers) == 2
        assert top_performers[0].name == "Jordan"
        assert top_performers[0].change_value == 92.5

        assert len(needs_attention) == 1
        assert needs_attention[0].name == "Pippen"
        assert "Missed 3 sessions" in needs_attention[0].reason

    async def test_get_insights_no_data(self, mock_db_session):
        """UTC-54-TC-02: Edge Case: No athletes, resulting in no insights."""
        # Arrange
        mock_empty_result = MagicMock()
        mock_empty_result.all.return_value = []
        mock_db_session.execute.side_effect = [mock_empty_result, mock_empty_result]

        # Act
        team_stats, top_performers, needs_attention = await _get_skill_and_player_insights(
            user_id=1, month_ago=MagicMock(), all_athletes=[], db=mock_db_session
        )

        # Assert
        assert team_stats.athletes_improved_percent == 0.0
        assert team_stats.top_trending_skill is None
        assert team_stats.skill_focus_distribution == []
        assert top_performers == []
        assert needs_attention == []

    async def test_get_insights_no_skill_activity(self, mock_db_session, mock_athletes_for_insights):
        """UTC-54-TC-03: Edge Case: Athletes exist, but no skills were trained this month."""
        # Arrange
        mock_skill_focus_result = MagicMock()
        mock_skill_focus_result.all.return_value = []  # No skills trained
        mock_absences_result = MagicMock()
        mock_absences_result.all.return_value = []  # Perfect attendance
        mock_db_session.execute.side_effect = [mock_skill_focus_result, mock_absences_result]

        # Act
        team_stats, top_performers, needs_attention = await _get_skill_and_player_insights(
            user_id=1, month_ago=MagicMock(), all_athletes=mock_athletes_for_insights, db=mock_db_session
        )

        # Assert
        assert team_stats.top_trending_skill is None
        assert team_stats.skill_focus_distribution == []
        assert len(top_performers) == 2
        assert needs_attention == []

    async def test_get_insights_perfect_attendance(self, mock_db_session, mock_athletes_for_insights):
        """UTC-54-TC-04: Edge Case: All athletes have perfect attendance."""
        # Arrange: Configure mock to be unpackable
        mock_skill_focus_row = MagicMock()
        mock_skill_focus_row.name = "Shooting"
        mock_skill_focus_row.count = 10
        mock_skill_focus_row.__iter__.return_value = iter([mock_skill_focus_row.name, mock_skill_focus_row.count])

        mock_skill_focus_result = MagicMock()
        mock_skill_focus_result.all.return_value = [mock_skill_focus_row]

        mock_absences_result = MagicMock()
        mock_absences_result.all.return_value = []  # No one missed a session
        mock_db_session.execute.side_effect = [mock_skill_focus_result, mock_absences_result]

        # Act
        _, _, needs_attention = await _get_skill_and_player_insights(
            user_id=1, month_ago=MagicMock(), all_athletes=mock_athletes_for_insights, db=mock_db_session
        )

        # Assert
        assert needs_attention == []


# --- Test ID: UTC-55 ---
class TestGenerateMotivationalHighlight:
    """Tests the _generate_motivational_highlight utility function."""

    @pytest.fixture
    def mock_stats_objects(self):
        """Provides a set of mock stats objects for testing."""
        mock_activity = MagicMock(spec=ActivityStats)
        mock_activity.sessions_conducted_month = MagicMock(spec=ComparativeStat)

        mock_engagement = MagicMock(spec=EngagementStats)
        mock_engagement.growth_insight = MagicMock(spec=GrowthInsight)

        mock_skill_stats = MagicMock(spec=TeamSkillStats)
        mock_skill_stats.top_trending_skill = MagicMock(spec=TopSkill)

        return mock_activity, mock_engagement, mock_skill_stats

    def test_high_impact_highlight(self, mock_stats_objects):
        """UTC-55-TC-01: Success: Trigger the high-impact highlight for session growth."""
        # Arrange: This is the highest priority condition.
        mock_activity, mock_engagement, mock_skill_stats = mock_stats_objects
        mock_activity.sessions_conducted_month.change_percent = 25.0  # > 20

        # Act
        highlight = _generate_motivational_highlight(mock_activity, mock_engagement, mock_skill_stats)

        # Assert
        assert isinstance(highlight, MotivationalHighlight)
        assert highlight.type == "HIGH_IMPACT"
        assert "Great momentum!" in highlight.message

    def test_team_growth_highlight(self, mock_stats_objects):
        """UTC-55-TC-02: Success: Trigger the team growth highlight for accelerating sign-ups."""
        # Arrange: First condition fails, second condition passes.
        mock_activity, mock_engagement, mock_skill_stats = mock_stats_objects
        mock_activity.sessions_conducted_month.change_percent = 10.0  # <= 20
        mock_engagement.growth_insight.trend_type = "accelerating"
        mock_engagement.growth_insight.narrative = "Your team's growth is accelerating!"

        # Act
        highlight = _generate_motivational_highlight(mock_activity, mock_engagement, mock_skill_stats)

        # Assert
        assert highlight.type == "TEAM_GROWTH"
        assert "accelerating" in highlight.message

    def test_skill_boost_highlight(self, mock_stats_objects):
        """UTC-55-TC-03: Success: Trigger the skill boost highlight."""
        # Arrange: First two conditions fail, third passes.
        mock_activity, mock_engagement, mock_skill_stats = mock_stats_objects
        mock_activity.sessions_conducted_month.change_percent = 10.0  # <= 20
        mock_activity.sessions_conducted_month.current = 15  # > 10
        mock_engagement.growth_insight.trend_type = "steady"
        mock_skill_stats.athletes_improved_percent = 60.0  # > 50
        mock_skill_stats.top_trending_skill.name = "Defense"

        # Act
        highlight = _generate_motivational_highlight(mock_activity, mock_engagement, mock_skill_stats)

        # Assert
        assert highlight.type == "SKILL_BOOST"
        assert "Your focus on Defense is paying off" in highlight.message

    def test_default_highlight(self, mock_stats_objects):
        """UTC-55-TC-04: Success: Fall back to the default highlight when no other conditions are met."""
        # Arrange: All specific conditions fail.
        mock_activity, mock_engagement, mock_skill_stats = mock_stats_objects
        mock_activity.sessions_conducted_month.change_percent = 5.0  # <= 20
        mock_activity.sessions_conducted_month.current = 8  # <= 10
        mock_engagement.growth_insight.trend_type = "steady"
        mock_skill_stats.athletes_improved_percent = 40.0  # <= 50

        # CORRECTED: Explicitly set top_trending_skill to None to prevent the AttributeError
        mock_skill_stats.top_trending_skill = None

        # Act
        highlight = _generate_motivational_highlight(mock_activity, mock_engagement, mock_skill_stats)

        # Assert
        assert highlight.type == "DEFAULT"
        assert "summary of your coaching activity" in highlight.message

    def test_skill_boost_no_top_skill(self, mock_stats_objects):
        """UTC-55-TC-05: Edge Case: Trigger skill boost but no top skill exists."""
        # Arrange: Same as TC-03, but with top_trending_skill as None
        mock_activity, mock_engagement, mock_skill_stats = mock_stats_objects
        mock_activity.sessions_conducted_month.change_percent = 10.0
        mock_activity.sessions_conducted_month.current = 15
        mock_engagement.growth_insight.trend_type = "steady"
        mock_skill_stats.athletes_improved_percent = 60.0
        mock_skill_stats.top_trending_skill = None  # Key difference

        # Act
        highlight = _generate_motivational_highlight(mock_activity, mock_engagement, mock_skill_stats)

        # Assert
        assert highlight.type == "SKILL_BOOST"
        assert "Your focus on key skills is paying off" in highlight.message  # Check for fallback text


# --- Test ID: UTC-56 ---
@pytest.mark.asyncio
# Decorators are applied from bottom to top.
@patch("src.analytics.service._generate_motivational_highlight")
@patch("src.analytics.service._get_skill_and_player_insights", new_callable=AsyncMock)
@patch("src.analytics.service._get_engagement_stats", new_callable=AsyncMock)
@patch("src.analytics.service._get_activity_and_efficiency_stats", new_callable=AsyncMock)
class TestGetCoachDashboardStats:
    """Tests the get_coach_dashboard_stats orchestrator function."""

    async def test_get_dashboard_stats_success(
            self, mock_get_activity, mock_get_engagement, mock_get_skill,
            mock_gen_highlight, mock_db_session
    ):
        """UTC-56-TC-01: Success: Orchestrate and assemble data from all helpers."""
        # Arrange: Create distinct mock objects for each helper's return value
        mock_activity_obj = MagicMock(spec=ActivityStats)
        mock_efficiency_obj = MagicMock(spec=EfficiencyStats)
        mock_engagement_obj = MagicMock(spec=EngagementStats)
        mock_athletes_list = [MagicMock(spec=Athlete)]
        mock_team_skill_obj = MagicMock(spec=TeamSkillStats)

        mock_top_improvers_list = [
            PlayerInsight(
                uuid=uuid4(), name="Player A", profile_image_url=None,
                reason="High Score", change_value=95.0, change_type="positive"
            )
        ]
        mock_needs_attention_list = [
            PlayerInsight(
                uuid=uuid4(), name="Player B", profile_image_url=None,
                reason="Low Attendance", change_value=3, change_type="negative"
            )
        ]

        mock_highlight_obj = MagicMock(spec=MotivationalHighlight)

        # Configure the return values for our patched functions
        mock_get_activity.return_value = (mock_activity_obj, mock_efficiency_obj)
        mock_get_engagement.return_value = (mock_engagement_obj, mock_athletes_list)
        mock_get_skill.return_value = (mock_team_skill_obj, mock_top_improvers_list, mock_needs_attention_list)
        mock_gen_highlight.return_value = mock_highlight_obj

        user_id = 1

        # Act
        result = await get_coach_dashboard_stats(user_id, mock_db_session)

        # Assert
        # 1. Verify all helper functions were called once
        mock_get_activity.assert_awaited_once()
        mock_get_engagement.assert_awaited_once()
        mock_get_skill.assert_awaited_once()
        mock_gen_highlight.assert_called_once_with(mock_activity_obj, mock_engagement_obj, mock_team_skill_obj)

        # 2. Verify the final object is constructed correctly
        assert isinstance(result, CoachStatData)
        assert result.activity is mock_activity_obj
        assert result.efficiency is mock_efficiency_obj
        assert result.engagement is mock_engagement_obj
        assert result.skill is mock_team_skill_obj

        # CORRECTED: Use '==' to check for value equality, not 'is' for object identity
        assert result.top_improvers == mock_top_improvers_list
        assert result.needs_attention == mock_needs_attention_list

        assert result.highlight is mock_highlight_obj

    async def test_get_dashboard_stats_helper_failure(
            self, mock_get_activity, mock_get_engagement, mock_get_skill,
            mock_gen_highlight, mock_db_session
    ):
        """UTC-56-TC-02: Failure: An underlying helper function raises an exception."""
        # Arrange: Make one of the helper functions raise an error
        mock_get_activity.side_effect = HTTPException(status_code=503, detail="Database Unavailable")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_coach_dashboard_stats(user_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Database Unavailable"

        # Ensure that subsequent helpers were not called
        mock_get_engagement.assert_not_called()
        mock_get_skill.assert_not_called()
        mock_gen_highlight.assert_not_called()

# --- Test ID: UTC-57 ---
@pytest.mark.asyncio
class TestCalculateDayOneAverageScore:
    """Tests the _calculate_day_one_average_score service helper function."""

    async def test_calculate_day_one_success(self, mock_db_session):
        """UTC-57-TC-01: Success: Calculate average score from the first day of activity."""
        # Arrange
        # Mock the first DB call to get the minimum date
        mock_min_date_result = MagicMock()
        mock_min_date_result.scalar_one_or_none.return_value = date(2025, 1, 15)

        # Mock the second DB call to get scores for that date
        mock_scores_result = MagicMock()
        mock_scores_result.scalars.return_value.all.return_value = [80.0, 90.0, 100.0]

        # Set up the side_effect to return the mocks in order
        mock_db_session.execute.side_effect = [mock_min_date_result, mock_scores_result]

        # Act
        average_score = await _calculate_day_one_average_score(athlete_id=1, db=mock_db_session)

        # Assert
        assert average_score == 90.0

    async def test_no_completions_for_athlete(self, mock_db_session):
        """UTC-57-TC-02: Edge Case: Athlete has no completions."""
        # Arrange: Mock the first DB call to find no minimum date
        mock_min_date_result = MagicMock()
        mock_min_date_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_min_date_result

        # Act
        average_score = await _calculate_day_one_average_score(athlete_id=1, db=mock_db_session)

        # Assert
        assert average_score == 0.0
        # Ensure the second DB call was never made
        assert mock_db_session.execute.call_count == 1

    async def test_no_scores_on_first_day(self, mock_db_session):
        """UTC-57-TC-03: Edge Case: Completions exist but have no final_score values."""
        # Arrange
        # Mock the first DB call to get the minimum date
        mock_min_date_result = MagicMock()
        mock_min_date_result.scalar_one_or_none.return_value = date(2025, 1, 15)

        # Mock the second DB call to return an empty list of scores
        mock_scores_result = MagicMock()
        mock_scores_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_min_date_result, mock_scores_result]

        # Act
        average_score = await _calculate_day_one_average_score(athlete_id=1, db=mock_db_session)

        # Assert
        assert average_score == 0.0


# --- Test ID: UTC-58 ---
@pytest.mark.asyncio
class TestCalculateImprovementSlope:
    """Tests the _calculate_improvement_slope service helper function."""

    def _create_mock_completion_row(self, dt, score):
        """Helper to create a mock row object for the DB query."""
        row = MagicMock()
        row.completed_at = dt
        row.final_score = float(score)
        return row

    async def test_calculate_positive_slope_success(self, mock_db_session):
        """UTC-58-TC-01: Success: Calculate a positive improvement slope."""
        # Arrange: Mock completions showing clear improvement over time
        completions = [
            self._create_mock_completion_row(datetime(2025, 1, 1), 70),
            self._create_mock_completion_row(datetime(2025, 1, 1), 80),  # Avg day 1: 75
            self._create_mock_completion_row(datetime(2025, 1, 8), 85),
            self._create_mock_completion_row(datetime(2025, 1, 8), 95),  # Avg day 2: 90
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = completions
        mock_db_session.execute.return_value = mock_result

        # Act
        slope = await _calculate_improvement_slope(athlete_id=1, db=mock_db_session)

        # Assert: Expected slope for points (0, 75) and (1, 90) is 15.0
        assert slope == pytest.approx(15.0)

    async def test_calculate_negative_slope(self, mock_db_session):
        """UTC-58-TC-02: Success: Calculate a negative improvement slope (decline)."""
        # Arrange
        completions = [
            self._create_mock_completion_row(datetime(2025, 2, 1), 90),  # Avg day 1: 90
            self._create_mock_completion_row(datetime(2025, 2, 8), 70),  # Avg day 2: 70
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = completions
        mock_db_session.execute.return_value = mock_result

        # Act
        slope = await _calculate_improvement_slope(athlete_id=1, db=mock_db_session)

        # Assert: Expected slope for points (0, 90) and (1, 70) is -20.0
        assert slope == pytest.approx(-20.0)

    async def test_insufficient_data(self, mock_db_session):
        """UTC-58-TC-03: Edge Case: Less than two data points (days) for regression."""
        # Arrange: Only one day of activity
        completions = [
            self._create_mock_completion_row(datetime(2025, 3, 1), 80),
            self._create_mock_completion_row(datetime(2025, 3, 1), 90),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = completions
        mock_db_session.execute.return_value = mock_result

        # Act
        slope = await _calculate_improvement_slope(athlete_id=1, db=mock_db_session)

        # Assert: Slope cannot be calculated with one point, should return 0
        assert slope == 0.0

    async def test_no_completions(self, mock_db_session):
        """UTC-58-TC-04: Edge Case: No completions exist for the athlete."""
        # Arrange
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Act
        slope = await _calculate_improvement_slope(athlete_id=1, db=mock_db_session)

        # Assert
        assert slope == 0.0


# --- Test ID: UTC-59 ---
@pytest.mark.asyncio
@patch("src.analytics.service._calculate_improvement_slope", new_callable=AsyncMock)
@patch("src.analytics.service._calculate_day_one_average_score", new_callable=AsyncMock)
class TestGetLeaderboardData:
    """Tests the get_leaderboard_data orchestrator function."""

    def _create_mock_athlete(self, name, current_score_avg, position_name="Guard"):
        """Helper to create a detailed mock athlete for leaderboard tests."""
        athlete = MagicMock(spec=Athlete)
        athlete.uuid = uuid4()
        athlete.name = name
        athlete.profile_image_url = f"{name.lower()}.png"

        # Mock skill_levels to produce the desired average score
        athlete.skill_levels = [MagicMock(current_score=current_score_avg)]
        athlete.skill_levels[0].current_score = current_score_avg

        # Mock positions
        mock_position = MagicMock()
        mock_position.name = position_name
        athlete.positions = [mock_position]
        return athlete

    async def test_get_leaderboard_success(
            self, mock_calc_day_one, mock_calc_slope, mock_db_session
    ):
        """UTC-59-TC-01: Success: Generate and correctly sort a leaderboard."""
        # Arrange
        # Create mock athletes with scores that will require sorting
        athlete_high = self._create_mock_athlete("High Scorer", 95.0)
        athlete_low = self._create_mock_athlete("Low Scorer", 75.0)
        athlete_mid = self._create_mock_athlete("Mid Scorer", 85.0)

        # Mock the DB query to return these athletes in an unsorted order
        mock_athlete_result = MagicMock()
        mock_athlete_result.scalars.return_value.unique.return_value.all.return_value = [
            athlete_mid, athlete_low, athlete_high
        ]
        mock_db_session.execute.return_value = mock_athlete_result

        # Mock the return values of the patched helper functions
        # The values can be the same for all for simplicity, as we test sorting on current_score
        mock_calc_day_one.return_value = 70.0
        mock_calc_slope.return_value = 2.5

        # Act
        leaderboard_response = await get_leaderboard_data(user_id=1, db=mock_db_session)

        # Assert
        assert isinstance(leaderboard_response, LeaderboardResponse)
        assert len(leaderboard_response.athletes) == 3

        # Verify the sorting and ranking are correct (based on current_score)
        assert leaderboard_response.athletes[0].name == "High Scorer"
        assert leaderboard_response.athletes[0].rank == 1
        assert leaderboard_response.athletes[1].name == "Mid Scorer"
        assert leaderboard_response.athletes[1].rank == 2
        assert leaderboard_response.athletes[2].name == "Low Scorer"
        assert leaderboard_response.athletes[2].rank == 3

        # Verify the data for one athlete is assembled correctly
        high_scorer_data = leaderboard_response.athletes[0]
        assert high_scorer_data.current_score == 95.0
        assert high_scorer_data.improvement_since_day_one == pytest.approx(25.0)  # 95 - 70
        assert high_scorer_data.improvement_slope == 2.5

    async def test_get_leaderboard_no_athletes(
            self, mock_calc_day_one, mock_calc_slope, mock_db_session
    ):
        """UTC-59-TC-02: Edge Case: The coach has no athletes."""
        # Arrange
        mock_athlete_result = MagicMock()
        mock_athlete_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_athlete_result

        # Act
        leaderboard_response = await get_leaderboard_data(user_id=1, db=mock_db_session)

        # Assert
        assert isinstance(leaderboard_response, LeaderboardResponse)
        assert len(leaderboard_response.athletes) == 0

        # Ensure helper functions were not called
        mock_calc_day_one.assert_not_called()
        mock_calc_slope.assert_not_called()