# src/course/schemas.py

from datetime import date, datetime
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, HttpUrl, Field, ConfigDict, computed_field
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


class TaskCompletionRead(BaseModel):
    athlete_uuid: UUID
    task_id: int
    final_score: Decimal
    scores_breakdown: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    time_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SessionRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    scheduled_date: datetime
    is_template: bool
    status: str
    tasks: List[SessionTaskRead]
    completions: List[TaskCompletionRead] = []
    total_duration_minutes: int
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def task_count(self) -> int:
        return len(self.tasks)

class SessionTemplateRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    total_duration_minutes: int
    tasks: List[SessionTaskRead]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def task_count(self) -> int:
        return len(self.tasks)


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

class FinalEvaluationData(BaseModel):
    scores: Dict[str, float]
    notes: Optional[str]
    time: int

class SessionReportData(BaseModel):
    course: Optional[CourseRead] = None
    session: SessionRead
    participatingAthletes: List[AttendeeResponse] = Field(..., alias="participatingAthletes")
    evaluations: Dict[str, FinalEvaluationData]
    totalSessionTime: int = Field(..., alias="totalSessionTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class TaskCompletionCreate(BaseModel):
    athlete_uuid: UUID
    task_id: int
    score: float = Field(..., ge=0, le=100)

    scores: Dict[int, float]
    notes: Optional[str] = None
    time: int

class SessionCompletionPayload(BaseModel):
    completions: List[TaskCompletionCreate]
    totalSessionTime: int

class EventItem(BaseModel):
    id: int
    title: str
    date: datetime
    type: Literal["course", "quick_session"]
    is_complete: bool
    course_id: Optional[int] = None
    course_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SessionStatusUpdate(BaseModel):
    status: str