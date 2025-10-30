# tests/unit/rubric/test_rubrics_constants.py

import pytest

from src.rubrics.constants import get_rubric, get_all_skill_names, SKILL_RUBRICS
from src.rubrics.schemas import RubricResponse


# --- Test ID: UTC-75 ---
class TestRubricService:
    """Tests the functions that provide rubric data."""

    def test_get_all_skill_names_success(self):
        """UTC-75-TC-01: Success: Ensure all skill names are returned."""
        expected_skills = [
            "Shooting", "Dribbling", "Passing", "Rebounding",
            "Defense", "Speed & Agility"
        ]
        skill_names = get_all_skill_names()

        assert isinstance(skill_names, list)
        # Use set for order-independent comparison
        assert set(skill_names) == set(expected_skills)
        assert len(skill_names) == len(expected_skills)

    @pytest.mark.parametrize("skill_name_case", ["shooting", "SHOOTING", "Shooting"])
    def test_get_rubric_success_case_insensitive(self, skill_name_case):
        """UTC-75-TC-02: Success: Retrieve a rubric with various casing."""
        rubric = get_rubric(skill_name_case)
        assert rubric is not None
        assert rubric["skill_name"] == "Shooting"
        assert "indicators" in rubric
        assert len(rubric["indicators"]) > 0

    def test_get_rubric_not_found(self):
        """UTC-75-TC-03: Failure: Return None for a skill that does not exist."""
        rubric = get_rubric("Juggling")
        assert rubric is None

    def test_all_rubrics_adhere_to_schema(self):
        """UTC-75-TC-04: Data Integrity: Ensure all defined rubrics match the Pydantic schema."""
        all_skill_names = get_all_skill_names()
        assert all_skill_names, "SKILL_RUBRICS constant should not be empty"

        for skill_name in all_skill_names:
            rubric_data = SKILL_RUBRICS[skill_name]

            # Combine the name with the data to match the RubricResponse structure
            full_rubric_data = {"skill_name": skill_name, **rubric_data}

            try:
                # Validate the data against the Pydantic model
                RubricResponse(**full_rubric_data)
            except Exception as e:
                pytest.fail(f"Rubric for '{skill_name}' failed validation: {e}")