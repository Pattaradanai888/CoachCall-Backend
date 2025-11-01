# src/course/insights.py

from typing import Any


def generate_session_insights(report_data: dict[str, Any]) -> dict[str, Any]:
    skill_comparison = report_data.get("skillComparisonData", {})
    evaluations = report_data.get("evaluations", {})
    participating_athletes = report_data.get("participatingAthletes", [])

    # Build athlete UUID to name mapping
    athlete_map = {
        str(athlete.uuid): athlete.name for athlete in participating_athletes
    }

    # Calculate per-athlete skill changes and notes
    athlete_notes = {}
    athlete_changes = {}  # Store for summary calculation

    for athlete_uuid, comparison in skill_comparison.items():
        # Handle Pydantic models - access attributes directly
        before_scores = comparison.before if hasattr(comparison, "before") else []
        after_scores = comparison.after if hasattr(comparison, "after") else []

        if not before_scores or not after_scores:
            continue

        # Calculate changes for each skill
        skill_changes = []
        for before_skill, after_skill in zip(before_scores, after_scores, strict=False):
            # Access Pydantic model attributes directly
            before_val = (
                before_skill.average_score
                if hasattr(before_skill, "average_score")
                else 0
            )
            after_val = (
                after_skill.average_score
                if hasattr(after_skill, "average_score")
                else 0
            )
            skill_name = (
                after_skill.skill_name if hasattr(after_skill, "skill_name") else ""
            )

            if before_val > 0:
                change_pct = ((after_val - before_val) / before_val) * 100
                skill_changes.append(
                    {"name": skill_name, "change": change_pct, "after": after_val}
                )

        # Store all changes for team average
        athlete_changes[athlete_uuid] = skill_changes

        # Generate note for this athlete
        note = _generate_athlete_note(
            athlete_uuid, skill_changes, evaluations, athlete_map
        )
        if note:
            athlete_notes[athlete_uuid] = note

    # Detect team-wide patterns from indicator data
    team_pattern = _detect_team_pattern(evaluations, athlete_map)

    # Generate overall summary
    summary = _generate_summary(athlete_changes, len(participating_athletes))

    # Generate action items based on findings
    action_items = _generate_action_items(
        athlete_notes, athlete_changes, team_pattern, athlete_map
    )

    return {
        "summary": summary,
        "athlete_notes": athlete_notes,
        "team_pattern": team_pattern,
        "action_items": action_items,
    }


def _generate_athlete_note(
    athlete_uuid: str,
    skill_changes: list[dict[str, Any]],
    evaluations: dict[str, Any],
    athlete_map: dict[str, str],
) -> str | None:
    athlete_name = athlete_map.get(athlete_uuid, "Athlete")

    if not skill_changes:
        return None

    # Find most significant change (positive or negative)
    significant_changes = [sc for sc in skill_changes if abs(sc["change"]) >= 5]

    if significant_changes:
        # Sort by absolute change to find most significant
        significant_changes.sort(key=lambda x: abs(x["change"]), reverse=True)
        top_change = significant_changes[0]

        change_val = top_change["change"]
        skill_name = top_change["name"]

        if change_val > 0:
            return (
                f"{athlete_name} demonstrated {change_val:.0f}% improvement "
                f"in {skill_name}"
            )
        else:
            return (
                f"{athlete_name} showed {abs(change_val):.0f}% decline in {skill_name} "
                "and requires additional focus"
            )

    # If no significant skill change, check for indicator weaknesses
    indicator_issue = _find_indicator_weakness(athlete_uuid, evaluations)
    if indicator_issue:
        return (
            f"{athlete_name} struggled with {indicator_issue['indicator']} "
            f"in {indicator_issue['skill']}"
        )

    # If no major changes or issues, provide neutral feedback
    return f"{athlete_name} maintained consistent performance across all skills"


def _find_indicator_weakness(
    athlete_uuid: str, evaluations: dict[str, Any]
) -> dict[str, str] | None:
    indicator_ratings = {}

    # Aggregate all indicator ratings for this athlete
    for eval_key, eval_data in evaluations.items():
        if not eval_key.startswith(athlete_uuid):
            continue

        scores = eval_data.get("scores", {})
        for skill_id, skill_data in scores.items():
            indicators = skill_data.get("indicators", {})
            for indicator_name, rating in indicators.items():
                key = (skill_id, indicator_name)
                if key not in indicator_ratings:
                    indicator_ratings[key] = []
                indicator_ratings[key].append(rating)

    # Find indicators where athlete consistently rated 1 (Needs Improvement)
    for (_skill_id, indicator_name), ratings in indicator_ratings.items():
        if len(ratings) >= 2:  # Multiple evaluations with same indicator
            avg_rating = sum(ratings) / len(ratings)
            if avg_rating <= 1.5:  # Consistently low
                # We don't have skill name here, so return generic
                return {"indicator": indicator_name, "skill": "related drills"}

    return None


def _detect_team_pattern(
    evaluations: dict[str, Any], athlete_map: dict[str, str]
) -> str | None:
    # Count how many athletes rated "1" for each indicator
    indicator_counts = {}  # (indicator_name, skill_name) -> count

    for _eval_key, eval_data in evaluations.items():
        scores = eval_data.get("scores", {})
        for _skill_id, skill_data in scores.items():
            indicators = skill_data.get("indicators", {})
            for indicator_name, rating in indicators.items():
                if rating == 1:  # Needs Improvement
                    key = indicator_name  # Simplified - just use indicator name
                    indicator_counts[key] = indicator_counts.get(key, 0) + 1

    # Find most common weakness with 3+ athletes
    common_weaknesses = [
        (ind, count) for ind, count in indicator_counts.items() if count >= 3
    ]

    if common_weaknesses:
        # Sort by count to get most common
        common_weaknesses.sort(key=lambda x: x[1], reverse=True)
        indicator, count = common_weaknesses[0]
        return (
            f"Multiple athletes ({count}) demonstrated difficulty with "
            f"{indicator} fundamentals"
        )

    return None


def _generate_summary(
    athlete_changes: dict[str, list[dict[str, Any]]], total_athletes: int
) -> str:
    if not athlete_changes:
        return "Session completed with all athletes participating in evaluations"

    # Calculate average change across all athletes and skills
    all_changes = []
    for changes in athlete_changes.values():
        all_changes.extend([c["change"] for c in changes])

    if not all_changes:
        return (
            "Session completed with baseline performance established for all athletes"
        )

    avg_change = sum(all_changes) / len(all_changes)

    # Generate appropriate summary based on average change
    if avg_change >= 3:
        return (
            "Productive session with measurable progress. Team averaged "
            f"{avg_change:.1f}% improvement across evaluated skills"
        )
    elif avg_change <= -3:
        return (
            "Challenging session requiring follow-up. Team performance decreased by "
            f"{abs(avg_change):.1f}% on average"
        )
    else:
        return (
            "Session completed with stable performance. "
            "Athletes maintained their skill levels with "
            f"{avg_change:.1f}% average variance"
        )


def _generate_action_items(
    athlete_notes: dict[str, str],
    athlete_changes: dict[str, list[dict[str, Any]]],
    team_pattern: str | None,
    athlete_map: dict[str, str],
) -> list[str]:
    action_items = []

    # Priority 1: Address team-wide pattern
    if team_pattern:
        # Extract the indicator from pattern message
        if "difficulty with" in team_pattern:
            indicator = team_pattern.split("difficulty with ")[1].split(
                " fundamentals"
            )[0]
            action_items.append(
                "Implement targeted drills focusing on "
                f"{indicator} technique in upcoming sessions"
            )

    # Priority 2: Address significant individual declines (>10%)
    athletes_needing_review = []
    for athlete_uuid, changes in athlete_changes.items():
        for change in changes:
            if change["change"] <= -10:
                athlete_name = athlete_map.get(athlete_uuid, "athlete")
                skill_name = change["name"]
                athletes_needing_review.append((athlete_name, skill_name))

    if athletes_needing_review and len(action_items) < 3:
        athlete_name, skill_name = athletes_needing_review[0]
        action_items.append(
            "Schedule individual review session with "
            f"{athlete_name} to address {skill_name} fundamentals"
        )

    # Priority 3: Reinforce fundamentals for struggling athletes
    struggling_indicators = []
    for note in athlete_notes.values():
        if "struggled with" in note:
            # Extract indicator from note
            parts = note.split("struggled with ")
            if len(parts) > 1:
                indicator = parts[1].split(" in ")[0]
                struggling_indicators.append(indicator)

    if struggling_indicators and len(action_items) < 3:
        unique_indicators = list(set(struggling_indicators))
        if unique_indicators:
            action_items.append(
                "Review and reinforce proper "
                f"{unique_indicators[0]} form with affected athletes"
            )

    # Priority 4: If no specific issues, provide general guidance
    if not action_items:
        action_items.append(
            "Continue current training regimen while monitoring for performance trends"
        )
        action_items.append(
            "Consider introducing progressive skill variations to "
            "challenge advancing athletes"
        )

    # Ensure we don't exceed 3 items
    return action_items[:3]