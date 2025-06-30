# tests/unit/athlete/test_schemas.py
from datetime import date
from unittest.mock import patch, MagicMock
import uuid

import pytest
from pydantic import ValidationError

from src.athlete.schemas import (
    AthleteCreate, AthleteUpdate, AthleteResponse, AthleteListResponse,
    GroupResponse, PositionResponse, ExperienceLevelResponse
)


# --- Test ID: UTC-07 ---
class TestAthleteCreateSchema:
    """Test the AthleteCreate schema validation, specifically age calculation."""

    @patch('src.athlete.schemas.date')
    def test_calculate_age_past_birthday(self, mock_date):
        """
        UTC-07-TC-01: Calculate age correctly for a past date of birth.
        """
        mock_date.today.return_value = date(2025, 6, 30)
        athlete_data = {"name": "Test Athlete", "date_of_birth": date(2005, 5, 10)}
        athlete = AthleteCreate(**athlete_data)
        assert athlete.age == 20

    @patch('src.athlete.schemas.date')
    def test_calculate_age_future_birthday(self, mock_date):
        """
        UTC-07-TC-02: Calculate age correctly when the birthday has not occurred yet this year.
        """
        mock_date.today.return_value = date(2025, 6, 30)
        athlete_data = {"name": "Test Athlete", "date_of_birth": date(2005, 8, 15)}
        athlete = AthleteCreate(**athlete_data)
        assert athlete.age == 19

    @patch('src.athlete.schemas.date')
    def test_calculate_age_iso_string_date(self, mock_date):
        """
        UTC-07-TC-03: Calculate age when date_of_birth is provided as an ISO format string.
        """
        mock_date.today.return_value = date(2025, 6, 30)
        mock_date.fromisoformat = date.fromisoformat
        athlete_data = {"name": "Test Athlete", "date_of_birth": "2005-05-10"}
        athlete = AthleteCreate(**athlete_data)
        assert athlete.age == 20


# --- Test ID: UTC-21 ---
class TestUpdateAndResponseSchemas:
    """Test the AthleteUpdate, AthleteResponse, and AthleteListResponse schemas."""

    def test_athlete_update_with_partial_data(self):
        """UTC-21-TC-01: Success: AthleteUpdate with partial data."""
        update_data = AthleteUpdate(name="Updated Name", height=190)
        assert update_data.name == "Updated Name"
        assert update_data.height == 190
        assert update_data.notes is None
        dumped = update_data.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "height" in dumped
        assert "notes" not in dumped

    def test_athlete_update_with_empty_relationship_lists(self):
        """UTC-21-TC-02: Success: AthleteUpdate with empty relationship lists."""
        update_data = AthleteUpdate(group_ids=[], position_ids=[])
        assert update_data.group_ids == []
        assert update_data.position_ids == []
        assert update_data.name is None

    def test_athlete_response_serialization(self):
        """UTC-21-TC-03: Success: AthleteResponse serialization from ORM object."""
        mock_exp_level = MagicMock()
        mock_exp_level.id = 10
        mock_exp_level.name = "Advanced"

        mock_group_a = MagicMock()
        mock_group_a.id = 1
        mock_group_a.name = "Group A"

        mock_group_b = MagicMock()
        mock_group_b.id = 2
        mock_group_b.name = "Group B"

        mock_pos = MagicMock()
        mock_pos.id = 3
        mock_pos.name = "Forward"

        mock_athlete = MagicMock()
        mock_athlete.uuid = uuid.uuid4()
        mock_athlete.user_id = 1
        mock_athlete.name = "Test Athlete"
        mock_athlete.date_of_birth = date(2000, 1, 1)
        mock_athlete.preferred_name = "Testy"
        mock_athlete.age = 25
        mock_athlete.height = 180
        mock_athlete.weight = 80
        mock_athlete.dominant_hand = "R"
        mock_athlete.phone_number = "123-456-7890"
        mock_athlete.emergency_contact_name = "Jane Doe"
        mock_athlete.emergency_contact_phone = "098-765-4321"
        mock_athlete.notes = "Some notes"
        mock_athlete.jersey_number = 23
        mock_athlete.profile_image_url = "http://example.com/img.png"
        mock_athlete.experience_level_id = 10
        mock_athlete.experience_level = mock_exp_level
        mock_athlete.groups = [mock_group_a, mock_group_b]
        mock_athlete.positions = [mock_pos]
        mock_athlete.skill_levels = []

        response = AthleteResponse.from_orm(mock_athlete)

        assert response.uuid == mock_athlete.uuid
        assert response.user_id == mock_athlete.user_id
        assert response.name == "Test Athlete"
        assert isinstance(response.experience_level, ExperienceLevelResponse)
        assert response.experience_level.name == "Advanced"
        assert len(response.groups) == 2
        assert isinstance(response.groups[0], GroupResponse)
        assert response.groups[0].name == "Group A"
        assert len(response.positions) == 1
        assert isinstance(response.positions[0], PositionResponse)
        assert response.positions[0].name == "Forward"

    def test_athlete_list_response_serialization(self):
        """UTC-21-TC-04: Success: AthleteListResponse serialization."""
        athlete_uuid = uuid.uuid4()
        data = {
            "uuid": athlete_uuid,
            "name": "List Athlete",
            "age": 22,
            "preferred_name": "Lis",
            "position": "Forward, Guard",
            "profile_image_url": "http://example.com/list.png"
        }
        response = AthleteListResponse(**data)
        assert response.uuid == athlete_uuid
        assert response.name == "List Athlete"
        assert response.age == 22
        assert response.position == "Forward, Guard"
        with pytest.raises(AttributeError):
            _ = response.user_id