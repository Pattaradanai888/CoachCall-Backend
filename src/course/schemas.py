# src/course/schemas.py

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from decimal import Decimal
from uuid import UUID

from src.athlete.schemas import PositionResponse


class SkillBase(BaseModel):
    name: str
    description: Optional[str] = None


class SkillCreate(SkillBase):
    pass


class SkillRead(SkillBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class TaskSkillWeightCreate(BaseModel):
    skill_id: int
    weight: float = Field(..., gt=0, le=1)


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int
    skill_weights: List[TaskSkillWeightCreate]


class SessionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scheduled_date: datetime
    is_template: bool = False
    tasks: List[TaskCreate]


class CourseCreate(BaseModel):
    name: str = Field(..., alias='title')
    description: Optional[str] = None
    cover_image_url: Optional[HttpUrl] = None
    start_date: date
    end_date: date
    sessions: List[SessionCreate]
    attendee_ids: Optional[List[UUID]] = []


class TaskSkillWeightRead(BaseModel):
    skill_id: int
    weight: Decimal
    skill_name: str
    model_config = ConfigDict(from_attributes=True)


class TaskRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    duration_minutes: int
    skill_weights: List[TaskSkillWeightRead]
    model_config = ConfigDict(from_attributes=True)

class SessionTaskRead(BaseModel):
    sequence: int
    task: TaskRead

    model_config = ConfigDict(from_attributes=True)


class SessionRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    scheduled_date: datetime
    is_template: bool
    status: str
    tasks: List[SessionTaskRead]
    model_config = ConfigDict(from_attributes=True)

class SessionTemplateRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    total_duration_minutes: int

    model_config = ConfigDict(from_attributes=True)


class AttendeeResponse(BaseModel):
    uuid: UUID
    name: str
    profile_image_url: Optional[str]
    positions: List[PositionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CourseRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    cover_image_url: Optional[str]
    is_archived: bool
    start_date: datetime
    end_date: datetime
    sessions: List[SessionRead]
    attendees: List[AttendeeResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CourseListRead(BaseModel):
    id: int
    name: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    attendee_count: int
    is_archived: bool
    cover_image_url: Optional[str]

    model_config = ConfigDict(from_attributes=True)