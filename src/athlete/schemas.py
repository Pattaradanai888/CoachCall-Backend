# src/athlete/schemas.py
from datetime import date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, model_validator



class GroupResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class PositionResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class ExperienceLevelResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class AthleteSkillResponse(BaseModel):
    skill_id: int
    current_score: Decimal
    skill_name: Optional[str] = None

    class Config:
        from_attributes = True



class AthleteBase(BaseModel):
    name: str
    preferred_name: Optional[str] = None
    age: Optional[int] = None  # Will be calculated
    height: Optional[int] = None
    weight: Optional[int] = None
    dominant_hand: Optional[str] = None
    date_of_birth: date
    phone_number: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None
    jersey_number: Optional[int] = None

    # Foreign Keys and M2M IDs for creation/update
    experience_level_id: Optional[int] = None
    group_ids: Optional[List[int]] = []
    position_ids: Optional[List[int]] = []



class AthleteCreate(AthleteBase):
    @model_validator(mode='before')
    def calculate_age(cls, values):
        if 'date_of_birth' in values and values['date_of_birth']:
            today = date.today()
            birth_date = values['date_of_birth']
            if isinstance(birth_date, str):
                birth_date = date.fromisoformat(birth_date)

            values['age'] = (today.year
                             - birth_date.year
                             - ((today.month, today.day) < (birth_date.month, birth_date.day)))
        return values


class AthleteUpdate(BaseModel):
    name: Optional[str] = None
    preferred_name: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    dominant_hand: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone_number: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None
    jersey_number: Optional[int] = None
    experience_level_id: Optional[int] = None
    group_ids: Optional[List[int]] = None
    position_ids: Optional[List[int]] = None


class AthleteResponse(AthleteBase):
    uuid: UUID
    profile_image_url: Optional[str] = None
    user_id: int

    experience_level: Optional[ExperienceLevelResponse] = None
    groups: List[GroupResponse] = []
    positions: List[PositionResponse] = []
    skill_levels: List[AthleteSkillResponse] = []

    class Config:
        from_attributes = True


class AthleteListResponse(BaseModel):
    uuid: UUID
    name: str
    age: Optional[int]
    preferred_name: Optional[str]
    position: str
    profile_image_url: Optional[str]

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupDeleteResponse(BaseModel):
    message: str
    deleted_group_id: int

class PositionCreate(BaseModel):
    name: str

class PositionDeleteResponse(BaseModel):
    message: str
    deleted_position_id: int


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