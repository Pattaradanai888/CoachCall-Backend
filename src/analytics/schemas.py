# src/analytics/schemas.py

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
