# src/analytics/service.py
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from uuid import UUID as PyUUID

from fastapi import HTTPException
from sqlalchemy import func, select, Date
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.athlete.models import Athlete, AthleteSkill
from src.course.models import TaskCompletion, Task, TaskSkillWeight, Skill
from . import constants
from . import utils
from .schemas import (
    AthleteSkillProgression,
    SkillScore,
    AthleteCreationStat,
    TrendDataPoint,
    AthleteInsights,
)


async def get_athlete_stats(user_id: int, db: AsyncSession) -> "AthleteCreationStat":
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date()

    # Time periods
    seven_days_ago = today_utc - timedelta(days=7)
    month_ago = today_utc - timedelta(days=30)
    six_days_ago = today_utc - timedelta(days=6)

    # Convert to datetime for comparison
    today_start = datetime.combine(today_utc, datetime.min.time(), tzinfo=timezone.utc)
    seven_days_ago_start = datetime.combine(
        seven_days_ago, datetime.min.time(), tzinfo=timezone.utc
    )
    six_days_ago_start = datetime.combine(
        six_days_ago, datetime.min.time(), tzinfo=timezone.utc
    )
    month_start = datetime.combine(month_ago, datetime.min.time(), tzinfo=timezone.utc)

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
    user_id: int, athlete_uuid: PyUUID, db: AsyncSession
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

    day_one_scores_dict = {skill_id: None for skill_id in all_user_skills.keys()}
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
    db: AsyncSession, athlete_id: int, exclude_session_id: Optional[int] = None
) -> Dict[int, float]:
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
                    # Apply EMA formula: new_ema = (new_value * alpha) + (old_ema * (1 - alpha))
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
