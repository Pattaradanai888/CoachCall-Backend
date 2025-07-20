# src/analytics/schemas.py
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class TrendDataPoint(BaseModel):
    date: str
    day_name: str
    formatted_date: str
    count: int


class AthleteInsights(BaseModel):
    week_change_percent: float | None
    peak_day: str | None
    avg_daily: float
    is_growing: bool | None


class AthleteCreationStat(BaseModel):
    today: int
    week: int
    month: int
    total: int
    trend: list[int]
    trend_detailed: list[TrendDataPoint]
    insights: AthleteInsights


class SkillScore(BaseModel):
    skill_id: int
    skill_name: str
    average_score: float


class AthleteSkillProgression(BaseModel):
    day_one: list[SkillScore]
    current: list[SkillScore]


class MotivationalHighlight(BaseModel):
    type: str
    message: str
    icon: str


class ActivityStats(BaseModel):
    sessions_conducted_month: int
    courses_created_month: int
    avg_sessions_per_week: float


class EfficiencyStats(BaseModel):
    template_reuse_rate: float
    sessions_from_template_month: int
    total_sessions_month: int


class EngagementStats(BaseModel):
    active_roster_count: int
    new_athletes_month: int
    team_attendance_rate: float | None


class SkillFocusItem(BaseModel):
    skill_name: str
    weight: float


class TopSkill(BaseModel):
    name: str


class TeamSkillStats(BaseModel):
    athletes_improved_percent: float
    top_trending_skill: TopSkill | None
    skill_focus_distribution: list[SkillFocusItem]


class PlayerInsight(BaseModel):
    uuid: UUID
    name: str
    profile_image_url: str | None
    reason: str
    change_value: float
    change_type: Literal["positive", "negative", "neutral"]


class CoachStatData(BaseModel):
    highlight: MotivationalHighlight
    activity: ActivityStats
    efficiency: EfficiencyStats
    engagement: EngagementStats
    skill: TeamSkillStats
    top_improvers: list[PlayerInsight]
    needs_attention: list[PlayerInsight]
