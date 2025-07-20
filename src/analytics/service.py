# src/analytics/service.py
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Date, Sequence, case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.athlete.models import Athlete, AthleteSkill
from src.course.models import (
    Course,
    Session,
    SessionAttendee,
    SessionTask,
    Skill,
    Task,
    TaskCompletion,
    TaskSkillWeight,
)

from ..auth.models import User
from . import constants, utils
from .schemas import (
    ActivityStats,
    AthleteCreationStat,
    AthleteInsights,
    AthleteSkillProgression,
    CoachStatData,
    EfficiencyStats,
    EngagementStats,
    MotivationalHighlight,
    PlayerInsight,
    SkillFocusItem,
    SkillScore,
    TeamSkillStats,
    TopSkill,
    TrendDataPoint,
)


async def get_athlete_stats(user_id: int, db: AsyncSession) -> "AthleteCreationStat":
    now_utc = datetime.now(UTC)
    today_utc = now_utc.date()

    # Time periods
    seven_days_ago = today_utc - timedelta(days=7)
    month_ago = today_utc - timedelta(days=30)
    six_days_ago = today_utc - timedelta(days=6)

    # Convert to datetime for comparison
    today_start = datetime.combine(today_utc, datetime.min.time(), tzinfo=UTC)
    seven_days_ago_start = datetime.combine(
        seven_days_ago, datetime.min.time(), tzinfo=UTC
    )
    six_days_ago_start = datetime.combine(six_days_ago, datetime.min.time(), tzinfo=UTC)
    month_start = datetime.combine(month_ago, datetime.min.time(), tzinfo=UTC)

    # Basic counts
    today_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id, Athlete.created_at >= today_start
        )
    )

    week_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id, Athlete.created_at >= seven_days_ago_start
        )
    )

    month_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id, Athlete.created_at >= month_start
        )
    )

    total_athletes = await db.scalar(
        select(func.count(Athlete.id)).where(Athlete.user_id == user_id)
    )

    # Get daily counts for the past 7 days
    daily_counts_query = (
        select(
            func.date(Athlete.created_at).label("date"),
            func.count(Athlete.id).label("count"),
        )
        .where(Athlete.user_id == user_id, Athlete.created_at >= six_days_ago_start)
        .group_by(func.date(Athlete.created_at))
        .order_by(func.date(Athlete.created_at))
    )

    daily_counts_result = await db.execute(daily_counts_query)
    daily_counts = daily_counts_result.all()

    # Create detailed trend data
    daily_counts_dict = {row.date: row.count for row in daily_counts}
    dates = [six_days_ago + timedelta(days=i) for i in range(7)]
    trend_data = []
    for date in dates:
        count = daily_counts_dict.get(date, 0)
        trend_data.append(
            {
                "date": date.isoformat(),
                "day_name": date.strftime("%a"),
                "formatted_date": date.strftime("%m/%d"),
                "count": count,
            }
        )

    # Calculate percentage changes for insights
    prev_week_start = seven_days_ago - timedelta(days=7)
    prev_week_start_dt = datetime.combine(prev_week_start, datetime.min.time())
    prev_week_count = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id,
            Athlete.created_at >= prev_week_start_dt,
            Athlete.created_at < seven_days_ago_start,
        )
    )
    trend_detailed = utils.format_trend_data(daily_counts_dict)
    week_change, peak_day, avg_daily, is_growing = utils.calculate_weekly_insights(
        week_count, prev_week_count, trend_detailed
    )

    return AthleteCreationStat(
        today=today_count or 0,
        week=week_count or 0,
        month=month_count or 0,
        total=total_athletes or 0,
        trend=[item["count"] for item in trend_detailed],
        trend_detailed=[TrendDataPoint(**item) for item in trend_detailed],
        insights=AthleteInsights(
            week_change_percent=week_change,
            peak_day=peak_day,
            avg_daily=avg_daily,
            is_growing=is_growing,
        ),
    )


async def get_athlete_skill_progression(
    user_id: int, athlete_uuid: UUID, db: AsyncSession
) -> AthleteSkillProgression:
    athlete_q = await db.execute(
        select(Athlete)
        .where(Athlete.uuid == athlete_uuid, Athlete.user_id == user_id)
        .options(selectinload(Athlete.skill_levels).selectinload(AthleteSkill.skill))
    )
    athlete = athlete_q.scalar_one_or_none()
    if not athlete:
        raise HTTPException(
            status_code=404, detail="Athlete not found or you do not have permission."
        )

    all_user_skills_q = await db.execute(
        select(Skill).where(Skill.user_id == user_id).order_by(Skill.id)
    )
    all_user_skills_list = all_user_skills_q.scalars().all()
    if not all_user_skills_list:
        return AthleteSkillProgression(day_one=[], current=[])
    all_user_skills = {skill.id: skill.name for skill in all_user_skills_list}

    completion_dates_q = await db.execute(
        select(func.distinct(func.cast(TaskCompletion.completed_at, Date)))
        .where(TaskCompletion.athlete_id == athlete.id)
        .order_by(func.cast(TaskCompletion.completed_at, Date))
    )
    completion_dates = completion_dates_q.scalars().all()

    day_one_scores_dict = dict.fromkeys(all_user_skills.keys())
    if completion_dates:
        first_date = completion_dates[0]
        day_one_completions_q = await db.execute(
            select(TaskCompletion)
            .where(
                TaskCompletion.athlete_id == athlete.id,
                func.cast(TaskCompletion.completed_at, Date) == first_date,
            )
            .options(
                selectinload(TaskCompletion.task)
                .selectinload(Task.skill_weights)
                .selectinload(TaskSkillWeight.skill)
            )
        )
        day_one_completions = day_one_completions_q.scalars().unique().all()
        skill_totals = defaultdict(
            lambda: {"total_weighted_score": 0.0, "total_weight": 0.0}
        )
        for comp in day_one_completions:
            if not comp.task or not comp.scores_breakdown:
                continue
            for sw in comp.task.skill_weights:
                if (
                    sw.skill_id in all_user_skills
                    and str(sw.skill_id) in comp.scores_breakdown
                ):
                    score = comp.scores_breakdown[str(sw.skill_id)]
                    weight = float(sw.weight)
                    skill_totals[sw.skill_id]["total_weighted_score"] += score * weight
                    skill_totals[sw.skill_id]["total_weight"] += weight

        for skill_id, data in skill_totals.items():
            if data["total_weight"] > 0:
                avg_score = data["total_weighted_score"] / data["total_weight"]
                day_one_scores_dict[skill_id] = round(avg_score, 2)

    day_one_scores = [
        SkillScore(
            skill_id=skill_id,
            skill_name=all_user_skills[skill_id],
            average_score=score if score is not None else 0.0,
        )
        for skill_id, score in sorted(day_one_scores_dict.items())
    ]

    athlete_current_scores_map = {
        ath_skill.skill_id: float(ath_skill.current_score)
        for ath_skill in athlete.skill_levels
    }
    current_scores = [
        SkillScore(
            skill_id=skill_id,
            skill_name=skill_name,
            average_score=athlete_current_scores_map.get(skill_id, 0.0),
        )
        for skill_id, skill_name in sorted(all_user_skills.items())
    ]

    return AthleteSkillProgression(day_one=day_one_scores, current=current_scores)


async def calculate_ema_skill_scores(
    db: AsyncSession, athlete_id: int, exclude_session_id: int | None = None
) -> dict[int, float]:
    query = (
        select(TaskCompletion)
        .where(TaskCompletion.athlete_id == athlete_id)
        .options(
            selectinload(TaskCompletion.task)
            .selectinload(Task.skill_weights)
            .selectinload(TaskSkillWeight.skill)
        )
        .order_by(TaskCompletion.completed_at.asc())
        .execution_options(populate_existing=True)
    )

    completions_q = await db.execute(query)
    all_completions = completions_q.scalars().unique().all()

    if not all_completions:
        return {}

    # Group completions by session_id and get their timestamps
    sessions_data = defaultdict(lambda: {"completions": [], "timestamp": None})
    for comp in all_completions:
        if comp.completed_at:
            sessions_data[comp.session_id]["completions"].append(comp)
            if sessions_data[comp.session_id]["timestamp"] is None:
                sessions_data[comp.session_id]["timestamp"] = comp.completed_at

    if not sessions_data:
        return {}

    # Sort sessions by timestamp to maintain chronological order
    sorted_sessions = sorted(sessions_data.items(), key=lambda x: x[1]["timestamp"])

    current_ema_scores = {}

    # Process sessions chronologically
    for session_id, session_data in sorted_sessions:
        # Skip this session if it's the one we want to exclude
        if exclude_session_id and session_id == exclude_session_id:
            continue

        session_skill_avg_data = defaultdict(
            lambda: {"total_weighted_score": 0.0, "total_weight": 0.0}
        )

        for comp in session_data["completions"]:
            if not comp.task or not comp.scores_breakdown:
                continue
            for sw in comp.task.skill_weights:
                if str(sw.skill_id) in comp.scores_breakdown:
                    score = comp.scores_breakdown[str(sw.skill_id)]
                    weight = float(sw.weight)
                    session_skill_avg_data[sw.skill_id]["total_weighted_score"] += (
                        score * weight
                    )
                    session_skill_avg_data[sw.skill_id]["total_weight"] += weight

        # Update EMA for this session
        for skill_id, data in session_skill_avg_data.items():
            if data["total_weight"] > 0:
                session_avg = data["total_weighted_score"] / data["total_weight"]
                if skill_id not in current_ema_scores:
                    # First time seeing this skill - initialize with the first score
                    current_ema_scores[skill_id] = session_avg
                else:
                    # Apply EMA formula:
                    # new_ema = (new_value * alpha) + (old_ema * (1 - alpha))
                    current_ema_scores[skill_id] = (
                        session_avg * constants.EMA_ALPHA
                    ) + (current_ema_scores[skill_id] * (1 - constants.EMA_ALPHA))

    return {skill_id: round(score, 2) for skill_id, score in current_ema_scores.items()}


async def update_athlete_skill_scores(athlete_id: int, db: AsyncSession):
    current_ema_scores = await calculate_ema_skill_scores(db, athlete_id)
    if not current_ema_scores:
        return

    upsert_values = [
        {
            "athlete_id": athlete_id,
            "skill_id": skill_id,
            "current_score": round(score, 2),
        }
        for skill_id, score in current_ema_scores.items()
    ]
    if not upsert_values:
        return

    stmt = pg_insert(AthleteSkill).values(upsert_values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["athlete_id", "skill_id"],
        set_={"current_score": stmt.excluded.current_score},
    )
    await db.execute(stmt)


async def _get_activity_and_efficiency_stats(
    user_id: int, month_ago: datetime, db: AsyncSession
) -> tuple[ActivityStats, EfficiencyStats]:
    # Use scheduled_date for sessions planned within the last month
    sessions_this_month_q = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.scheduled_date >= month_ago,
            Session.is_template.is_(False),
        )
    )
    sessions_this_month = sessions_this_month_q.scalars().all()
    sessions_conducted_month = len(sessions_this_month)

    # A better "template reuse" logic: sessions belonging to a course are planned
    sessions_from_template_month = sum(
        1 for s in sessions_this_month if s.course_id is not None
    )
    template_reuse_rate = (
        round((sessions_from_template_month / sessions_conducted_month) * 100, 1)
        if sessions_conducted_month > 0
        else 0.0
    )

    courses_created_month = await db.scalar(
        select(func.count(Course.id)).where(
            Course.user_id == user_id, Course.start_date >= month_ago
        )
    )

    total_sessions = await db.scalar(
        select(func.count(Session.id)).where(
            Session.user_id == user_id, Session.is_template.is_(False)
        )
    )
    user_creation_date = await db.scalar(
        select(User.created_at).where(User.id == user_id)
    )
    # Handle case where user_creation_date might be None
    total_weeks = (
        (datetime.now(UTC) - user_creation_date).days / 7 if user_creation_date else 1
    )
    avg_sessions_per_week = (
        round(total_sessions / total_weeks, 1) if total_weeks > 0 else 0.0
    )

    activity = ActivityStats(
        sessions_conducted_month=sessions_conducted_month,
        courses_created_month=courses_created_month or 0,
        avg_sessions_per_week=avg_sessions_per_week,
    )
    efficiency = EfficiencyStats(
        template_reuse_rate=template_reuse_rate,
        sessions_from_template_month=sessions_from_template_month,
        total_sessions_month=sessions_conducted_month,
    )
    return activity, efficiency


async def _get_engagement_stats(
    user_id: int, month_ago: datetime, db: AsyncSession
) -> tuple[EngagementStats, Sequence[Athlete]]:
    """Gathers stats on athlete roster and attendance."""
    athletes_q = await db.execute(
        select(Athlete)
        .where(
            Athlete.user_id == user_id,
            # PEP8/Ruff Correction: Use is_(True) for boolean checks
            Athlete.is_active.is_(True),
        )
        .options(selectinload(Athlete.skill_levels).selectinload(AthleteSkill.skill))
    )
    all_athletes = athletes_q.scalars().unique().all()
    active_roster_count = len(all_athletes)

    new_athletes_month = await db.scalar(
        select(func.count(Athlete.id)).where(
            Athlete.user_id == user_id, Athlete.created_at >= month_ago
        )
    )

    # REAL attendance rate calculation
    attendance_q = await db.execute(
        select(
            func.count(SessionAttendee.athlete_id).label("total"),
            func.sum(case((SessionAttendee.was_present, 1), else_=0)).label("present"),
        )
        .join(SessionAttendee.session)
        .where(Session.user_id == user_id, Session.scheduled_date >= month_ago)
    )
    attendance_counts = attendance_q.first()
    team_attendance_rate = None
    if attendance_counts and attendance_counts.total > 0:
        team_attendance_rate = round(
            (attendance_counts.present / attendance_counts.total) * 100, 1
        )

    engagement = EngagementStats(
        active_roster_count=active_roster_count,
        new_athletes_month=new_athletes_month or 0,
        team_attendance_rate=team_attendance_rate,
    )
    return engagement, all_athletes


async def _get_skill_and_player_insights(
    user_id: int, month_ago: datetime, all_athletes: Sequence[Athlete], db: AsyncSession
) -> tuple[TeamSkillStats, list[PlayerInsight], list[PlayerInsight]]:
    """Gathers stats on team skill development and identifies key players."""

    # Real metric: "how many athletes have recorded scores".
    athletes_with_scores = sum(1 for a in all_athletes if a.skill_levels)
    athletes_improved_percent = (
        round((athletes_with_scores / len(all_athletes)) * 100, 1)
        if all_athletes
        else 0.0
    )

    # Skill Focus Distribution - based on tasks in recent sessions
    skill_weights_q = await db.execute(
        select(Skill.name, func.count(TaskSkillWeight.task_id).label("count"))
        .select_from(Skill)
        .join(TaskSkillWeight, Skill.id == TaskSkillWeight.skill_id)
        .join(SessionTask, TaskSkillWeight.task_id == SessionTask.task_id)
        .join(Session, SessionTask.session_id == Session.id)
        .where(Session.user_id == user_id, Session.scheduled_date >= month_ago)
        .group_by(Skill.name)
        .order_by(func.count(TaskSkillWeight.task_id).desc())
    )
    skill_focus_raw = skill_weights_q.all()
    total_tasks_with_skills = sum(s.count for s in skill_focus_raw)
    skill_focus_distribution = (
        [
            SkillFocusItem(
                skill_name=name,
                weight=round((count / total_tasks_with_skills) * 100, 1),
            )
            for name, count in skill_focus_raw
        ]
        if total_tasks_with_skills > 0
        else []
    )

    top_skill = (
        TopSkill(name=skill_focus_distribution[0].skill_name)
        if skill_focus_distribution
        else None
    )

    team_skill_stats = TeamSkillStats(
        athletes_improved_percent=athletes_improved_percent,
        top_trending_skill=top_skill,
        skill_focus_distribution=skill_focus_distribution,
    )

    # Player Insights: Top Performers (based on current average score)
    top_performers = []
    for athlete in all_athletes:
        if athlete.skill_levels:
            avg_score = sum(s.current_score for s in athlete.skill_levels) / len(
                athlete.skill_levels
            )
            top_performers.append(
                PlayerInsight(
                    uuid=athlete.uuid,
                    name=athlete.name,
                    profile_image_url=athlete.profile_image_url,
                    reason=f"Avg Score: {avg_score:.1f}",
                    change_value=float(avg_score),
                    change_type="positive",
                )
            )

    # Player Insights: Needs Attention (based on missed sessions)
    absences_q = await db.execute(
        select(Athlete, func.count(SessionAttendee.session_id).label("missed_count"))
        .join(SessionAttendee, SessionAttendee.athlete_id == Athlete.id)
        .join(Session, Session.id == SessionAttendee.session_id)
        .where(
            Athlete.user_id == user_id,
            Session.scheduled_date >= month_ago,
            SessionAttendee.was_present.is_(False),
        )
        .group_by(Athlete.id)
        .order_by(func.count(SessionAttendee.session_id).desc())
        .limit(3)
    )
    needs_attention = [
        PlayerInsight(
            uuid=athlete.uuid,
            name=athlete.name,
            profile_image_url=athlete.profile_image_url,
            reason=f"Missed {missed_count} sessions",
            change_value=missed_count,
            change_type="negative",
        )
        for athlete, missed_count in absences_q.all()
    ]

    return (
        team_skill_stats,
        sorted(top_performers, key=lambda p: p.change_value, reverse=True)[:3],
        needs_attention,
    )


def _generate_motivational_highlight(
    activity: ActivityStats, skill_stats: TeamSkillStats
) -> MotivationalHighlight:
    """Generates a dynamic highlight message based on the collected stats."""
    top_skill_name = (
        skill_stats.top_trending_skill.name
        if skill_stats.top_trending_skill
        else "key skills"
    )

    msg = ""
    if (
        activity.sessions_conducted_month > 15
        and skill_stats.athletes_improved_percent > 75
    ):
        msg = (
            f"Incredible work! You ran {activity.sessions_conducted_month} "
            f"sessions and improved over {skill_stats.athletes_improved_percent}% "
            "of your team!"
        )
        return MotivationalHighlight(
            type="HIGH_IMPACT", message=msg, icon="mdi:rocket-launch"
        )

    if skill_stats.top_trending_skill:
        msg = (
            f"Your focus on {top_skill_name} is paying off, with "
            f"{skill_stats.athletes_improved_percent}% of athletes showing progress."
        )
        return MotivationalHighlight(
            type="SKILL_BOOST", message=msg, icon="mdi:trending-up"
        )

    return MotivationalHighlight(
        type="DEFAULT",
        message="Here's a summary of your coaching activity and its impact.",
        icon="mdi:chart-bar",
    )


async def get_coach_dashboard_stats(user_id: int, db: AsyncSession) -> "CoachStatData":
    """
    Provides a comprehensive overview of coach activity, efficiency,
    and impact on athlete development for the main dashboard.
    """
    now = datetime.now(UTC)
    month_ago = now - timedelta(days=30)

    activity, efficiency = await _get_activity_and_efficiency_stats(
        user_id, month_ago, db
    )
    engagement, all_athletes = await _get_engagement_stats(user_id, month_ago, db)
    (
        skill_stats,
        top_improvers,
        needs_attention,
    ) = await _get_skill_and_player_insights(user_id, month_ago, all_athletes, db)

    highlight = _generate_motivational_highlight(activity, skill_stats)

    return CoachStatData(
        highlight=highlight,
        activity=activity,
        efficiency=efficiency,
        engagement=engagement,
        skill=skill_stats,
        top_improvers=top_improvers,
        needs_attention=needs_attention,
    )
