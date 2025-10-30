# tests/unit/rubric/test_rubrics_schemas.py

import pytest
from pydantic import ValidationError

from src.rubrics.schemas import (
    IndicatorDescription,
    Indicator,
    RubricResponse,
    AvailableSkillsResponse,
)


# --- Test ID: UTC-74 ---
class TestRubricSchemas:
    """Tests the Pydantic models in the rubrics module."""

    def test_indicator_description_success(self):
        """UTC-74-TC-01: Success: Create IndicatorDescription with valid data."""
        data = {
            "needs_improvement": "Struggles with concept",
            "developing": "Shows basic understanding",
            "proficient": "Masters the concept",
        }
        model = IndicatorDescription(**data)
        assert model.proficient == "Masters the concept"

    def test_indicator_description_missing_field_failure(self):
        """UTC-74-TC-02: Failure: Create IndicatorDescription with a missing field."""
        data = {
            "needs_improvement": "Struggles with concept",
            "developing": "Shows basic understanding",
        }
        with pytest.raises(ValidationError):
            IndicatorDescription(**data)

    def test_indicator_success(self):
        """UTC-74-TC-03: Success: Create Indicator with valid data."""
        data = {
            "title": "Ball Control",
            "descriptions": {
                1: "Loses the ball frequently",
                3: "Maintains control under pressure",
                5: "Executes advanced moves with ease",
            }
        }
        model = Indicator(**data)
        assert model.title == "Ball Control"
        assert model.descriptions[3] == "Maintains control under pressure"

    def test_indicator_invalid_key_type_failure(self):
        """UTC-74-TC-04: Failure: Create Indicator with non-integer keys in descriptions."""
        data = {
            "title": "Ball Control",
            "descriptions": {
                "one": "Loses the ball frequently",
            }
        }
        with pytest.raises(ValidationError):
            Indicator(**data)

    def test_rubric_response_success(self):
        """UTC-74-TC-05: Success: Create RubricResponse with nested valid data."""
        data = {
            "skill_name": "Dribbling",
            "indicators": [
                {
                    "title": "Ball Control",
                    "descriptions": {1: "Poor", 3: "Average", 5: "Excellent"}
                },
                {
                    "title": "Speed",
                    "descriptions": {1: "Slow", 3: "Moderate", 5: "Fast"}
                }
            ]
        }
        model = RubricResponse(**data)
        assert model.skill_name == "Dribbling"
        assert len(model.indicators) == 2
        assert isinstance(model.indicators[0], Indicator)
        assert model.indicators[1].title == "Speed"

    def test_rubric_response_invalid_nested_data_failure(self):
        """UTC-74-TC-06: Failure: Create RubricResponse with invalid data in the indicators list."""
        data = {
            "skill_name": "Dribbling",
            "indicators": [
                {
                    # Missing 'title' field, making this indicator invalid
                    "descriptions": {1: "Poor", 3: "Average", 5: "Excellent"}
                }
            ]
        }
        with pytest.raises(ValidationError):
            RubricResponse(**data)

    def test_available_skills_response_success(self):
        """UTC-74-TC-07: Success: Create AvailableSkillsResponse with valid data."""
        data = {"skills": ["Shooting", "Dribbling", "Passing"]}
        model = AvailableSkillsResponse(**data)
        assert model.skills == ["Shooting", "Dribbling", "Passing"]

    def test_available_skills_response_invalid_type_in_list_failure(self):
        """UTC-74-TC-08: Failure: Create AvailableSkillsResponse with non-string items in the list."""
        data = {"skills": ["Shooting", 123, "Passing"]}
        with pytest.raises(ValidationError):
            AvailableSkillsResponse(**data)