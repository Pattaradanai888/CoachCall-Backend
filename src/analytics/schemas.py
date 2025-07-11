# src/analytics/schemas.py
from typing import Optional, List
from pydantic import BaseModel


class TrendDataPoint(BaseModel):
    date: str
    day_name: str
    formatted_date: str
    count: int


class AthleteInsights(BaseModel):
    week_change_percent: Optional[float]
    peak_day: Optional[str]
    avg_daily: float
    is_growing: Optional[bool]


class AthleteCreationStat(BaseModel):
    today: int
    week: int
    month: int
    total: int
    trend: list[int]
    trend_detailed: List[TrendDataPoint]
    insights: AthleteInsights


class SkillScore(BaseModel):
    skill_id: int
    skill_name: str
    average_score: float


class AthleteSkillProgression(BaseModel):
    day_one: List[SkillScore]
    current: List[SkillScore]
