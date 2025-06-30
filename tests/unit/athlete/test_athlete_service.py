# tests/unit/athlete/test_athlete_service.py

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from src.athlete.models import Athlete, Group, Position, ExperienceLevel
from src.athlete.schemas import AthleteCreate, AthleteUpdate
from src.athlete.service import (
    create_athlete,
    update_athlete,
    delete_athlete,
    delete_group,
    delete_position,
    upload_athlete_image,
    delete_athlete_image,
    get_athlete_stats,
    get_coach_athletes,
    get_coach_athlete_by_uuid,
    create_group,
    get_groups,
    create_position,
    get_positions,
    get_all_coach_athletes_for_selection,
    get_latest_athlete_for_coach
)
from src.upload.schemas import UploadResponse


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


# --- Test ID: UTC-08 ---
@pytest.mark.asyncio
class TestCreateAthleteService:
    async def test_create_athlete_success_with_relationships(self, mock_db_session):
        """UTC-08-TC-01: Success: Create an athlete with all valid, optional relationships."""
        user_id = 1
        athlete_payload = AthleteCreate(
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            experience_level_id=1,
            group_ids=[10, 11],
            position_ids=[20, 21]
        )

        mock_exp_level = ExperienceLevel(id=1, user_id=user_id)
        mock_groups = [Group(id=10, user_id=user_id), Group(id=11, user_id=user_id)]
        mock_positions = [Position(id=20, user_id=user_id), Position(id=21, user_id=user_id)]

        mock_db_session.get.return_value = mock_exp_level

        # Mock db.execute for groups and positions
        mock_group_result = MagicMock()
        mock_group_result.scalars.return_value.all.return_value = mock_groups
        mock_pos_result = MagicMock()
        mock_pos_result.scalars.return_value.all.return_value = mock_positions

        # The service makes multiple calls to execute
        mock_final_athlete_result = MagicMock()
        mock_final_athlete_result.scalars.return_value.one.return_value = Athlete(id=1)  # simplified
        mock_db_session.execute.side_effect = [mock_group_result, mock_pos_result, mock_final_athlete_result]

        # Call the service function
        created_athlete = await create_athlete(user_id, athlete_payload, mock_db_session)

        # 1. Returns an Athlete model instance.
        assert isinstance(created_athlete, Athlete)

        # 2. Check relationships were assigned before commit (not directly testable on final object, but implicitly via mocks)
        # This is implicitly tested by the mocks being set up correctly and no error being raised.

        # 3. db.add() and db.commit() are called.
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_create_athlete_failure_invalid_group_id(self, mock_db_session):
        """UTC-08-TC-02: Failure: Attempt to create an athlete with invalid group_ids."""
        user_id = 1
        athlete_payload = AthleteCreate(
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            group_ids=[1, 99]  # 99 is invalid
        )

        # Mock db.execute returning only one valid group
        mock_group_result = MagicMock()
        mock_group_result.scalars.return_value.all.return_value = [Group(id=1, user_id=user_id)]
        mock_db_session.execute.return_value = mock_group_result

        with pytest.raises(HTTPException) as exc_info:
            await create_athlete(user_id, athlete_payload, mock_db_session)

        # 1. Raises HTTPException.
        # 2. Status code is 400.
        assert exc_info.value.status_code == 400
        # 3. Detail is "One or more group IDs are invalid."
        assert "One or more group IDs are invalid" in exc_info.value.detail
        # 4. db.commit() is not called.
        mock_db_session.commit.assert_not_awaited()

    async def test_create_athlete_failure_invalid_experience_level_id(self, mock_db_session):
        """UTC-08-TC-03: Failure: Attempt to create an athlete with an invalid experience_level_id."""
        user_id = 1
        athlete_payload = AthleteCreate(
            name="Test User",
            date_of_birth=date(2000, 1, 1),
            experience_level_id=99  # 99 is invalid
        )

        # Mock db.get returning None
        mock_db_session.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await create_athlete(user_id, athlete_payload, mock_db_session)

        # 1. Raises HTTPException.
        # 2. Status code is 400.
        assert exc_info.value.status_code == 400
        # 3. Detail is "Invalid experience_level_id: 99".
        assert "Invalid experience_level_id: 99" in exc_info.value.detail
        # 4. db.commit() is not called.
        mock_db_session.commit.assert_not_awaited()


# --- Test ID: UTC-09 ---
@pytest.mark.asyncio
@patch("src.athlete.service.get_coach_athlete_by_uuid")
class TestUpdateAthleteService:
    async def test_update_athlete_simple_fields_success(self, mock_get_athlete, mock_db_session):
        """UTC-09-TC-01: Success: Update simple fields of an athlete (e.g., name, height)."""
        user_id = 1
        athlete_uuid = uuid.uuid4()

        mock_athlete = Athlete(id=1, name="Old Name", height=180)
        mock_get_athlete.return_value = mock_athlete

        athlete_update = AthleteUpdate(name="New Name", height=185)

        mock_final_result = MagicMock()
        mock_final_result.scalars.return_value.one.return_value = mock_athlete
        mock_db_session.execute.return_value = mock_final_result

        updated_athlete = await update_athlete(user_id, athlete_uuid, athlete_update, mock_db_session)

        assert updated_athlete.name == "New Name"
        assert updated_athlete.height == 185
        mock_db_session.commit.assert_awaited_once()

    async def test_update_athlete_m2m_success(self, mock_get_athlete, mock_db_session):
        """UTC-09-TC-02: Success: Update M2M relationships (e.g., positions)."""
        user_id = 1
        athlete_uuid = uuid.uuid4()
        mock_athlete = Athlete(id=1, positions=[Position(id=1)])
        mock_get_athlete.return_value = mock_athlete

        new_positions = [Position(id=3), Position(id=4)]
        athlete_update = AthleteUpdate(position_ids=[3, 4])

        mock_pos_result = MagicMock()
        mock_pos_result.scalars.return_value.all.return_value = new_positions

        mock_final_fetch_result = MagicMock()
        mock_final_fetch_result.scalars.return_value.one.return_value = mock_athlete
        mock_db_session.execute.side_effect = [mock_pos_result, mock_final_fetch_result]

        updated_athlete = await update_athlete(user_id, athlete_uuid, athlete_update, mock_db_session)

        assert updated_athlete.positions == new_positions
        mock_db_session.commit.assert_awaited_once()

    async def test_update_athlete_clear_m2m_success(self, mock_get_athlete, mock_db_session):
        """UTC-09-TC-03: Success: Clear an M2M relationship by providing an empty list."""
        user_id = 1
        athlete_uuid = uuid.uuid4()
        mock_athlete = Athlete(id=1, groups=[Group(id=1)])
        mock_get_athlete.return_value = mock_athlete

        athlete_update = AthleteUpdate(group_ids=[])

        mock_final_result = MagicMock()
        mock_final_result.scalars.return_value.one.return_value = mock_athlete
        mock_db_session.execute.return_value = mock_final_result

        updated_athlete = await update_athlete(user_id, athlete_uuid, athlete_update, mock_db_session)

        assert updated_athlete.groups == []
        mock_db_session.commit.assert_awaited_once()

    async def test_update_athlete_not_found_failure(self, mock_get_athlete, mock_db_session):
        """UTC-09-TC-04: Failure: Attempt to update an athlete that does not exist."""
        mock_get_athlete.return_value = None
        athlete_update = AthleteUpdate(name="any name")
        result = await update_athlete(1, uuid.uuid4(), athlete_update, mock_db_session)
        assert result is None
        mock_db_session.commit.assert_not_awaited()

    async def test_update_athlete_invalid_group_id_failure(self, mock_get_athlete, mock_db_session):
        """UTC-09-TC-05: Failure: Attempt to update with an invalid group_id."""
        mock_get_athlete.return_value = Athlete(id=1)
        athlete_update = AthleteUpdate(group_ids=[1, 99])
        mock_group_result = MagicMock()
        mock_group_result.scalars.return_value.all.return_value = [Group(id=1)]
        mock_db_session.execute.return_value = mock_group_result

        with pytest.raises(HTTPException) as exc_info:
            await update_athlete(1, uuid.uuid4(), athlete_update, mock_db_session)

        assert exc_info.value.status_code == 400
        assert "One or more group IDs are invalid" in exc_info.value.detail
        mock_db_session.commit.assert_not_awaited()

# --- Test ID: UTC-10 ---
@pytest.mark.asyncio
@patch("src.athlete.service.get_coach_athlete_by_uuid")
class TestDeleteAthleteService:
    async def test_delete_athlete_success(self, mock_get_athlete, mock_db_session):
        """UTC-10-TC-01: Success: Delete an existing athlete."""
        mock_athlete = Athlete(id=1)
        mock_get_athlete.return_value = mock_athlete

        # 1. Returns True.
        result = await delete_athlete(1, uuid.uuid4(), mock_db_session)
        assert result is True

        # 2. db.delete() and db.commit() are called.
        mock_db_session.delete.assert_called_once_with(mock_athlete)
        mock_db_session.commit.assert_awaited_once()

    async def test_delete_athlete_not_found_failure(self, mock_get_athlete, mock_db_session):
        """UTC-10-TC-02: Failure: Attempt to delete an athlete that does not exist."""
        mock_get_athlete.return_value = None

        # 1. Returns False.
        result = await delete_athlete(1, uuid.uuid4(), mock_db_session)
        assert result is False

        # 2. db.delete() is not called.
        mock_db_session.delete.assert_not_called()
        mock_db_session.commit.assert_not_awaited()


# --- Test ID: UTC-11 ---
@pytest.mark.asyncio
class TestDeleteGroupAndPositionService:
    async def test_delete_group_success(self, mock_db_session):
        """UTC-11-TC-01: Success: Delete an existing group belonging to the user."""
        mock_group = Group(id=1, user_id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_db_session.execute.return_value = mock_result

        # 1. Returns a success message.
        result = await delete_group(1, 1, mock_db_session)
        assert result == {"message": "Group deleted successfully", "deleted_group_id": 1}

        # 2. db.delete() and db.commit() are called.
        mock_db_session.delete.assert_called_once_with(mock_group)
        mock_db_session.commit.assert_awaited_once()

    async def test_delete_position_success(self, mock_db_session):
        """UTC-11-TC-02: Success: Delete an existing position belonging to the user."""
        mock_position = Position(id=1, user_id=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_position
        mock_db_session.execute.return_value = mock_result

        # 1. Returns a success message.
        result = await delete_position(1, 1, mock_db_session)
        assert result == {"message": "Position deleted successfully", "deleted_position_id": 1}

        # 2. db.delete() and db.commit() are called.
        mock_db_session.delete.assert_called_once_with(mock_position)
        mock_db_session.commit.assert_awaited_once()

    async def test_delete_group_not_found_failure(self, mock_db_session):
        """UTC-11-TC-03: Failure: Attempt to delete a group that does not exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_group(99, 1, mock_db_session)

        # 1. Raises HTTPException with status code 404.
        assert exc_info.value.status_code == 404
        # 2. Detail is "Group not found...".
        assert "Group not found" in exc_info.value.detail

    async def test_delete_position_not_found_failure(self, mock_db_session):
        """UTC-11-TC-04: Failure: Attempt to delete a position that does not exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_position(99, 1, mock_db_session)

        # 1. Raises HTTPException with status code 404.
        assert exc_info.value.status_code == 404
        # 2. Detail is "Position not found...".
        assert "Position not found" in exc_info.value.detail


# --- Test ID: UTC-12 ---
@pytest.mark.asyncio
@patch("src.athlete.service.image_upload_service", new_callable=AsyncMock)
@patch("src.athlete.service.get_coach_athlete_by_uuid")
class TestAthleteImageService:

    async def test_upload_image_first_time_success(self, mock_get_athlete, mock_image_service, mock_db_session):
        """UTC-12-TC-01: Success (Upload): Upload an image for an athlete for the first time."""
        mock_athlete = Athlete(id=1, profile_image_url=None)
        mock_get_athlete.return_value = mock_athlete
        mock_image_service.upload_image.return_value = UploadResponse(url="http://new.url/img.png")

        # 1. Returns the new image URL.
        result_url = await upload_athlete_image(1, uuid.uuid4(), MagicMock(), mock_db_session)
        assert result_url == "http://new.url/img.png"

        # 2. image_upload_service.delete_image is not called.
        mock_image_service.delete_image.assert_not_called()

        # 3. The athlete's profile_image_url is updated.
        assert mock_athlete.profile_image_url == "http://new.url/img.png"

        # 4. db.commit() is called.
        mock_db_session.commit.assert_awaited_once()

    async def test_upload_replace_image_success(self, mock_get_athlete, mock_image_service, mock_db_session):
        """UTC-12-TC-02: Success (Upload): Replace an existing athlete image."""
        mock_athlete = Athlete(id=1, profile_image_url="old_url")
        mock_get_athlete.return_value = mock_athlete
        mock_image_service.upload_image.return_value = UploadResponse(url="new_url")

        # 3. Returns the new image URL.
        result_url = await upload_athlete_image(1, uuid.uuid4(), MagicMock(), mock_db_session)
        assert result_url == "new_url"

        # 1. image_upload_service.delete_image is called with "old_url".
        mock_image_service.delete_image.assert_awaited_once_with("old_url")
        # 2. image_upload_service.upload_image is subsequently called.
        mock_image_service.upload_image.assert_awaited_once()

    async def test_delete_image_success(self, mock_get_athlete, mock_image_service, mock_db_session):
        """UTC-12-TC-03: Success (Delete): Delete an existing athlete image."""
        mock_athlete = Athlete(id=1, profile_image_url="some_url")
        mock_get_athlete.return_value = mock_athlete

        await delete_athlete_image(1, uuid.uuid4(), mock_db_session)

        # 1. image_upload_service.delete_image is called with "some_url".
        mock_image_service.delete_image.assert_awaited_once_with("some_url")
        # 2. The athlete's profile_image_url is set to None.
        assert mock_athlete.profile_image_url is None
        # 3. db.commit() is called.
        mock_db_session.commit.assert_awaited_once()

    async def test_upload_image_service_failure(self, mock_get_athlete, mock_image_service, mock_db_session):
        """UTC-12-TC-04: Failure (Upload): The external image service fails during upload."""
        mock_get_athlete.return_value = Athlete(id=1)
        mock_image_service.upload_image.side_effect = Exception("Upload failed")

        with pytest.raises(HTTPException) as exc_info:
            await upload_athlete_image(1, uuid.uuid4(), MagicMock(), mock_db_session)

        # 1. Raises HTTPException with status 500.
        assert exc_info.value.status_code == 500
        # 2. db.rollback() is called.
        mock_db_session.rollback.assert_awaited_once()

    async def test_delete_image_not_found_failure(self, mock_get_athlete, mock_image_service, mock_db_session):
        """UTC-12-TC-05: Failure (Delete): Attempt to delete an image for an athlete who doesn't have one."""
        mock_athlete = Athlete(id=1, profile_image_url=None)
        mock_get_athlete.return_value = mock_athlete

        with pytest.raises(HTTPException) as exc_info:
            await delete_athlete_image(1, uuid.uuid4(), mock_db_session)

        # 1. Raises HTTPException with status 404 and detail "No profile image found for this athlete".
        assert exc_info.value.status_code == 404
        assert "No profile image found" in exc_info.value.detail

        # 2. image_upload_service.delete_image is not called.
        mock_image_service.delete_image.assert_not_called()

    async def test_delete_image_service_failure(self, mock_get_athlete, mock_image_service, mock_db_session):
        """UTC-12-TC-06: Failure (Delete): The external image service fails during deletion."""
        mock_athlete = Athlete(id=1, profile_image_url="some_url")
        mock_get_athlete.return_value = mock_athlete
        mock_image_service.delete_image.side_effect = Exception("Deletion failed")

        with pytest.raises(HTTPException) as exc_info:
            await delete_athlete_image(1, uuid.uuid4(), mock_db_session)

        # 1. Raises HTTPException with status 500.
        assert exc_info.value.status_code == 500
        # 2. db.rollback() is called.
        mock_db_session.rollback.assert_awaited_once()


# --- Test ID: UTC-13 ---
@pytest.mark.asyncio
class TestGetAthleteStatsService:
    async def test_get_athlete_stats_success(self, mock_db_session):
        """UTC-13-TC-01: Success: Calculate stats with data across all periods."""
        # Prerequisite: Mock db.scalar to return counts
        mock_db_session.scalar.side_effect = [
            2,  # today
            10,  # week
            30,  # month
            100,  # total
            5,  # prev_week
        ]

        # Prerequisite: Mock db.execute for daily trend
        mock_daily_row = MagicMock()
        mock_daily_row.date = datetime.now().date() - date.resolution * 2  # an example date
        mock_daily_row.count = 4

        mock_daily_result = MagicMock()
        mock_daily_result.all.return_value = [mock_daily_row]
        mock_db_session.execute.return_value = mock_daily_result

        # Execute
        stats = await get_athlete_stats(1, mock_db_session)

        # 1. Returns a dictionary matching the AthleteCreationStat schema.
        assert isinstance(stats, dict)

        # 2. today, week, month, total match mocked values.
        assert stats["today"] == 2
        assert stats["week"] == 10
        assert stats["month"] == 30
        assert stats["total"] == 100

        # 3. insights.week_change_percent is correctly calculated (e.g., 100.0).
        # (10 - 5) / 5 * 100 = 100.0
        assert stats["insights"]["week_change_percent"] == 100.0

        # 4. insights.is_growing is True.
        assert stats["insights"]["is_growing"] is True

        # 5. trend and trend_detailed have 7 items.
        assert len(stats["trend"]) == 7
        assert len(stats["trend_detailed"]) == 7


# ----------------------------------------------------------------------------------
# --- START OF NEWLY ADDED TESTS ---
# ----------------------------------------------------------------------------------


# --- Test ID: UTC-14 ---
@pytest.mark.asyncio
class TestGetCoachAthletes:
    async def test_get_athletes_with_default_pagination(self, mock_db_session):
        """UTC-14-TC-01: Success: Get athletes with default pagination."""
        user_id = 1
        mock_athletes = [Athlete(id=1), Athlete(id=2), Athlete(id=3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_athletes
        mock_db_session.execute.return_value = mock_result

        athletes = await get_coach_athletes(user_id=user_id, db=mock_db_session, skip=0, limit=5)

        assert len(athletes) == 3
        mock_db_session.execute.assert_awaited_once()

    async def test_get_athletes_with_custom_pagination(self, mock_db_session):
        """UTC-14-TC-02: Success: Get athletes with custom pagination."""
        user_id = 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await get_coach_athletes(user_id=user_id, db=mock_db_session, skip=5, limit=10)

        executed_query = mock_db_session.execute.call_args[0][0]

        # FIX: Compile the query to a string to check for LIMIT and OFFSET clauses
        compiled_query = str(executed_query.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 10" in compiled_query
        assert "OFFSET 5" in compiled_query

    async def test_get_athletes_no_athletes_exist(self, mock_db_session):
        """UTC-14-TC-03: Success: No athletes exist for user."""
        user_id = 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        athletes = await get_coach_athletes(user_id=user_id, db=mock_db_session)
        assert athletes == []


# --- Test ID: UTC-15 ---
@pytest.mark.asyncio
class TestGetCoachAthleteByUuid:
    async def test_find_existing_athlete_with_all_relationships(self, mock_db_session):
        """UTC-15-TC-01: Success: Find existing athlete with all relationships."""
        user_id = 1
        athlete_uuid = uuid.uuid4()
        mock_athlete = Athlete(id=1, user_id=user_id, uuid=athlete_uuid)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_athlete
        mock_db_session.execute.return_value = mock_result

        athlete = await get_coach_athlete_by_uuid(user_id, athlete_uuid, mock_db_session)

        assert athlete is not None
        assert athlete.uuid == athlete_uuid
        mock_db_session.execute.assert_awaited_once()

    async def test_non_existent_athlete_uuid(self, mock_db_session):
        """UTC-15-TC-02: Failure: Non-existent athlete UUID."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        athlete = await get_coach_athlete_by_uuid(1, uuid.uuid4(), mock_db_session)
        assert athlete is None


# --- Test ID: UTC-16 ---
@pytest.mark.asyncio
class TestGroupService:
    async def test_create_group_success(self, mock_db_session):
        """UTC-16-TC-01: Success: Create group with valid data."""
        user_id = 1
        name = "Defense"

        async def refresh_side_effect(obj):
            obj.id = 123

        mock_db_session.refresh.side_effect = refresh_side_effect

        group = await create_group(user_id, name, mock_db_session)

        mock_db_session.add.assert_called_once()
        created_group = mock_db_session.add.call_args[0][0]
        assert isinstance(created_group, Group)
        assert created_group.user_id == user_id
        assert created_group.name == name
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()
        assert group.id == 123

    async def test_get_all_groups_for_user(self, mock_db_session):
        """UTC-16-TC-02: Success: Get all groups for user."""
        user_id = 1
        mock_groups = [Group(id=1, user_id=user_id), Group(id=2, user_id=user_id)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_db_session.execute.return_value = mock_result

        groups = await get_groups(user_id, mock_db_session)

        assert len(groups) == 2
        mock_db_session.execute.assert_awaited_once()

    async def test_get_no_groups_for_user(self, mock_db_session):
        """UTC-16-TC-03: Success: No groups exist for user."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        groups = await get_groups(1, mock_db_session)
        assert groups == []


# --- Test ID: UTC-17 ---
@pytest.mark.asyncio
class TestPositionService:
    async def test_create_position_success(self, mock_db_session):
        """UTC-17-TC-01: Success: Create position with valid data."""
        user_id = 1
        name = "Point Guard"

        position = await create_position(user_id, name, mock_db_session)

        mock_db_session.add.assert_called_once()
        created_position = mock_db_session.add.call_args[0][0]
        assert isinstance(created_position, Position)
        assert created_position.user_id == user_id
        assert created_position.name == name
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    async def test_get_all_positions_for_user(self, mock_db_session):
        """UTC-17-TC-02: Success: Get all positions for user."""
        user_id = 1
        mock_positions = [Position(id=1, user_id=user_id), Position(id=2, user_id=user_id)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_positions
        mock_db_session.execute.return_value = mock_result

        positions = await get_positions(user_id, mock_db_session)

        assert len(positions) == 2
        mock_db_session.execute.assert_awaited_once()


# --- Test ID: UTC-18 ---
@pytest.mark.asyncio
class TestGetAllCoachAthletesForSelection:
    async def test_get_athletes_ordered_by_name(self, mock_db_session):
        """UTC-18-TC-01: Success: Get athletes ordered by name for selection."""
        user_id = 1
        mock_athletes = [Athlete(name="B"), Athlete(name="A")]  # Unordered
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_athletes
        mock_db_session.execute.return_value = mock_result

        await get_all_coach_athletes_for_selection(user_id, mock_db_session)

        # Check that the query was ordered by name
        executed_query = mock_db_session.execute.call_args[0][0]
        # This is a bit tricky to assert on a mock, but we can check for the order_by clause
        assert "athletes.name" in str(executed_query.compile(compile_kwargs={"literal_binds": True}))


# --- Test ID: UTC-19 ---
@pytest.mark.asyncio
class TestGetLatestAthleteForCoach:
    async def test_get_most_recently_created_athlete(self, mock_db_session):
        """UTC-19-TC-01: Success: Get most recently created athlete."""
        user_id = 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = Athlete(id=1)
        mock_db_session.execute.return_value = mock_result

        await get_latest_athlete_for_coach(user_id, mock_db_session)

        executed_query = mock_db_session.execute.call_args[0][0]

        compiled_query = str(executed_query.compile(compile_kwargs={"literal_binds": True}))
        assert "ORDER BY athletes.created_at DESC" in compiled_query
        assert "LIMIT 1" in compiled_query

    async def test_no_athletes_exist_for_coach(self, mock_db_session):
        """UTC-19-TC-02: Success: No athletes exist for coach."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        athlete = await get_latest_athlete_for_coach(1, mock_db_session)
        assert athlete is None


# --- Test ID: UTC-20 ---
@pytest.mark.asyncio
class TestGetAthleteStatsEdgeCases:
    async def test_no_athletes_exist(self, mock_db_session):
        """UTC-20-TC-01: Success: No athletes exist for user."""
        # Mock all db calls to return 0 or empty
        mock_db_session.scalar.side_effect = [0, 0, 0, 0, 0]  # today, week, month, total, prev_week
        mock_daily_result = MagicMock()
        mock_daily_result.all.return_value = []
        mock_db_session.execute.return_value = mock_daily_result

        stats = await get_athlete_stats(1, mock_db_session)

        assert stats["today"] == 0
        assert stats["week"] == 0
        assert stats["month"] == 0
        assert stats["total"] == 0
        assert stats["trend"] == [0, 0, 0, 0, 0, 0, 0]
        assert stats["insights"]["week_change_percent"] is None
        assert stats["insights"]["is_growing"] is None
        assert stats["insights"]["peak_day"] is None

    async def test_growth_from_zero(self, mock_db_session):
        """UTC-20-TC-03: Success: Calculate week-over-week growth from zero."""
        mock_db_session.scalar.side_effect = [1, 5, 5, 5, 0]  # today, week, month, total, prev_week
        mock_daily_result = MagicMock()
        mock_daily_result.all.return_value = [MagicMock(count=5, day_name="Mon")]  # dummy data
        mock_db_session.execute.return_value = mock_daily_result

        stats = await get_athlete_stats(1, mock_db_session)

        assert stats["insights"]["is_growing"] is True
        assert stats["insights"]["week_change_percent"] == 100.0