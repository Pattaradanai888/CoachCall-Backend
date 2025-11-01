# tests/unit/course/test_course_insights.py

import pytest
from collections import namedtuple
from uuid import uuid4
from unittest.mock import patch, MagicMock


from src.course.insights import generate_session_insights, _generate_summary, _generate_athlete_note, \
    _find_indicator_weakness, _detect_team_pattern, _generate_action_items

MockAthlete = namedtuple("MockAthlete", ["uuid", "name"])
MockSkillScore = namedtuple("MockSkillScore", ["skill_name", "average_score"])
MockComparison = namedtuple("MockComparison", ["before", "after"])


# --- Test ID: UTC-76 ---
@patch("src.course.insights._generate_action_items")
@patch("src.course.insights._detect_team_pattern")
@patch("src.course.insights._generate_summary")
@patch("src.course.insights._generate_athlete_note")
class TestGenerateSessionInsights:
    """Tests the main orchestrator function, generate_session_insights."""

    def test_orchestrator_calls_helpers(
            self, mock_gen_note, mock_gen_summary, mock_detect_pattern, mock_gen_actions
    ):
        """UTC-76-TC-01: Success: The main function calls all its helpers and assembles the results."""
        # Arrange
        athlete1_uuid = uuid4()
        mock_report_data = {
            "participatingAthletes": [MockAthlete(uuid=athlete1_uuid, name="Jordan")],
            "skillComparisonData": {
                str(athlete1_uuid): MockComparison(
                    before=[MockSkillScore("Shooting", 80)], after=[MockSkillScore("Shooting", 90)]
                )
            },
            "evaluations": {},
        }

        # Mock return values for helpers
        mock_gen_summary.return_value = "Test Summary"
        mock_gen_note.return_value = "Test Note"
        mock_detect_pattern.return_value = "Test Pattern"
        mock_gen_actions.return_value = ["Test Action"]

        # Act
        insights = generate_session_insights(mock_report_data)

        # Assert
        mock_gen_summary.assert_called_once()
        mock_gen_note.assert_called_once()
        mock_detect_pattern.assert_called_once()
        mock_gen_actions.assert_called_once()

        assert insights["summary"] == "Test Summary"
        assert insights["athlete_notes"][str(athlete1_uuid)] == "Test Note"
        assert insights["team_pattern"] == "Test Pattern"
        assert insights["action_items"] == ["Test Action"]


# --- Test ID: UTC-77 ---
class TestGenerateSummary:
    """Tests the _generate_summary helper function."""

    @pytest.mark.parametrize("changes, athlete_count, expected_string", [
        ({"uuid1": [{"change": 10}, {"change": 5}]}, 2, "Productive session"),  # TC-01
        ({"uuid1": [{"change": -15}, {"change": -5}]}, 2, "Challenging session"),  # TC-02
        ({"uuid1": [{"change": 1}, {"change": -1}]}, 2, "stable performance"),  # TC-03
        ({}, 2, "Session completed with all athletes"),  # TC-04
        ({"uuid1": []}, 1, "baseline performance established"),  # TC-05
    ])
    def test_summary_narratives(self, changes, athlete_count, expected_string):
        """UTC-77-TC-01 to TC-05: Test various summary scenarios."""
        summary = _generate_summary(changes, athlete_count)
        assert expected_string in summary


# --- Test ID: UTC-78 ---
class TestGenerateAthleteNote:
    """Tests the _generate_athlete_note helper function."""

    def test_priority_1_significant_change(self):
        """UTC-78-TC-01: Success: Note for significant positive or negative change."""
        athlete_map = {"uuid1": "Jordan"}
        pos_changes = [{"name": "Shooting", "change": 15.0}]
        neg_changes = [{"name": "Defense", "change": -12.0}]

        pos_note = _generate_athlete_note("uuid1", pos_changes, {}, athlete_map)
        assert "15% improvement in Shooting" in pos_note

        neg_note = _generate_athlete_note("uuid1", neg_changes, {}, athlete_map)
        assert "12% decline in Defense" in neg_note

    def test_priority_2_indicator_weakness(self):
        """UTC-78-TC-02: Success: Note for indicator weakness when no significant change exists."""
        athlete_map = {"uuid1": "Pippen"}
        no_sig_changes = [{"name": "Passing", "change": 2.0}]
        evals = {
            "uuid1-task1": {"scores": {"Passing": {"indicators": {"Stance": 1}}}},
            "uuid1-task2": {"scores": {"Passing": {"indicators": {"Stance": 1}}}},
        }
        note = _generate_athlete_note("uuid1", no_sig_changes, evals, athlete_map)
        assert "Pippen struggled with Stance" in note

    def test_priority_3_neutral_feedback(self):
        """UTC-78-TC-03: Success: Note for consistent performance (fallback)."""
        athlete_map = {"uuid1": "Rodman"}
        no_sig_changes = [{"name": "Passing", "change": 2.0}]
        note = _generate_athlete_note("uuid1", no_sig_changes, {}, athlete_map)
        assert "maintained consistent performance" in note


# --- Test ID: UTC-79 ---
class TestFindIndicatorWeakness:
    """Tests the _find_indicator_weakness helper function."""

    def test_finds_consistent_weakness(self):
        """UTC-79-TC-01: Success: Identifies a consistent weakness (avg rating <= 1.5)."""
        evals = {
            "uuid1-task1": {"scores": {"1": {"indicators": {"Stance": 1}}}},
            "uuid1-task2": {"scores": {"1": {"indicators": {"Stance": 1}}}},
        }
        weakness = _find_indicator_weakness("uuid1", evals)
        assert weakness is not None
        assert weakness["indicator"] == "Stance"

    def test_no_consistent_weakness(self):
        """UTC-79-TC-02: Failure: Does not identify a weakness if ratings are inconsistent or too high."""
        evals = {
            "uuid1-task1": {"scores": {"1": {"indicators": {"Stance": 1}}}},
            "uuid1-task2": {"scores": {"1": {"indicators": {"Stance": 3}}}},  # Avg is 2.0
        }
        weakness = _find_indicator_weakness("uuid1", evals)
        assert weakness is None

    def test_insufficient_data(self):
        """UTC-79-TC-03: Edge Case: Does not identify weakness with only one data point."""
        evals = {"uuid1-task1": {"scores": {"1": {"indicators": {"Stance": 1}}}}}
        weakness = _find_indicator_weakness("uuid1", evals)
        assert weakness is None


# --- Test ID: UTC-80 ---
class TestDetectTeamPattern:
    """Tests the _detect_team_pattern helper function."""

    def test_finds_team_pattern(self):
        """UTC-80-TC-01: Success: Identifies a pattern when 3+ athletes have the same weakness."""
        evals = {
            "uuid1-task": {"scores": {"1": {"indicators": {"Stance": 1}}}},
            "uuid2-task": {"scores": {"1": {"indicators": {"Stance": 1}}}},
            "uuid3-task": {"scores": {"1": {"indicators": {"Stance": 1}}}},
        }
        pattern = _detect_team_pattern(evals, {})
        assert "Multiple athletes (3) demonstrated difficulty with Stance" in pattern

    def test_no_team_pattern(self):
        """UTC-80-TC-02: Failure: No pattern found if fewer than 3 athletes have the same weakness."""
        evals = {
            "uuid1-task": {"scores": {"1": {"indicators": {"Stance": 1}}}},
            "uuid2-task": {"scores": {"1": {"indicators": {"Stance": 1}}}},
        }
        pattern = _detect_team_pattern(evals, {})
        assert pattern is None


# --- Test ID: UTC-81 ---
class TestGenerateActionItems:
    """Tests the _generate_action_items helper function."""

    def test_priority_1_team_pattern(self):
        """UTC-81-TC-01: Success: Action item for a team-wide pattern."""
        team_pattern = "Multiple athletes (4) demonstrated difficulty with Footwork fundamentals"
        items = _generate_action_items({}, {}, team_pattern, {})
        assert "Implement targeted drills focusing on Footwork" in items[0]

    def test_priority_2_individual_decline(self):
        """UTC-81-TC-02: Success: Action item for a significant individual decline."""
        athlete_map = {"uuid1": "Jordan"}
        changes = {"uuid1": [{"name": "Shooting", "change": -15.0}]}
        items = _generate_action_items({}, changes, None, athlete_map)
        assert "Schedule individual review session with Jordan" in items[0]

    def test_priority_3_struggling_indicator(self):
        """UTC-81-TC-03: Success: Action item for an indicator-based struggle."""
        notes = {"uuid1": "Jordan struggled with Stance in related drills"}
        items = _generate_action_items(notes, {}, None, {})
        assert "Review and reinforce proper Stance form" in items[0]

    def test_priority_4_default_items(self):
        """UTC-81-TC-04: Success: Returns default action items when no specific issues are found."""
        items = _generate_action_items({}, {}, None, {})
        assert len(items) >= 1
        assert "Continue current training regimen" in items[0]