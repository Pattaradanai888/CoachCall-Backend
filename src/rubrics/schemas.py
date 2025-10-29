# src/rubrics/schemas.py
from pydantic import BaseModel


class IndicatorDescription(BaseModel):
    needs_improvement: str
    developing: str
    proficient: str


class Indicator(BaseModel):
    title: str
    descriptions: dict[int, str]


class RubricResponse(BaseModel):
    skill_name: str
    indicators: list[Indicator]


class AvailableSkillsResponse(BaseModel):
    skills: list[str]
