# src/course/schemas.py

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field

from src.analytics.schemas import SkillScore
from src.athlete.schemas import PositionResponse


class SkillBase(BaseModel):
    name: str
    description: str | None = None


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
    description: str | None = None
    duration_minutes: int
    skill_weights: list[TaskSkillWeightCreate]


class SessionCreate(BaseModel):
    name: str
    description: str | None = None
    scheduled_date: datetime
    is_template: bool = False
    tasks: list[TaskCreate]


class CourseCreate(BaseModel):
    name: str = Field(..., alias="title")
    description: str | None = None
    cover_image_url: HttpUrl | None = None
    start_date: date
    end_date: date
    sessions: list[SessionCreate]
    attendee_ids: list[UUID] | None = []


class TaskSkillWeightRead(BaseModel):
    skill_id: int
    weight: Decimal
    skill_name: str
    model_config = ConfigDict(from_attributes=True)


class TaskRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    duration_minutes: int
    skill_weights: list[TaskSkillWeightRead]
    model_config = ConfigDict(from_attributes=True)


class SessionTaskRead(BaseModel):
    sequence: int
    task: TaskRead

    model_config = ConfigDict(from_attributes=True)


class TaskCompletionRead(BaseModel):
    athlete_uuid: UUID
    task_id: int
    final_score: Decimal
    scores_breakdown: dict[str, float] | None = None
    notes: str | None = None
    time_seconds: int | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionRead(BaseModel):
    id: int
    name: str
    description: str | None
    scheduled_date: datetime
    completed_at: datetime | None = None
    is_template: bool
    status: str
    tasks: list[SessionTaskRead]
    completions: list[TaskCompletionRead] = []
    total_duration_minutes: int
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def task_count(self) -> int:
        return len(self.tasks)


class SessionTemplateRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    total_duration_minutes: int
    tasks: list[SessionTaskRead]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def task_count(self) -> int:
        return len(self.tasks)


class AttendeeResponse(BaseModel):
    uuid: UUID
    name: str
    profile_image_url: str | None
    positions: list[PositionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CourseRead(BaseModel):
    id: int
    name: str
    description: str | None
    cover_image_url: str | None
    is_archived: bool
    start_date: datetime
    end_date: datetime
    sessions: list[SessionRead]
    attendees: list[AttendeeResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CourseListRead(BaseModel):
    id: int
    name: str
    start_date: datetime | None
    end_date: datetime | None
    attendee_count: int
    is_archived: bool
    cover_image_url: str | None

    model_config = ConfigDict(from_attributes=True)


class FinalEvaluationData(BaseModel):
    scores: dict[str, float]
    notes: str | None
    time: int


class SessionSkillComparison(BaseModel):
    before: list[SkillScore]
    after: list[SkillScore]


class CourseContextForReport(BaseModel):
    id: int
    name: str
    description: str | None
    cover_image_url: str | None
    is_archived: bool
    start_date: datetime
    end_date: datetime
    attendees: list[AttendeeResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SessionReportData(BaseModel):
    course: CourseContextForReport | None = None
    session: SessionRead
    skill_comparison_data: dict[str, SessionSkillComparison] = Field(
        ..., alias="skillComparisonData"
    )
    participating_athletes: list[AttendeeResponse] = Field(
        ..., alias="participatingAthletes"
    )
    evaluations: dict[str, FinalEvaluationData]
    total_session_time: int = Field(..., alias="totalSessionTime")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TaskCompletionCreate(BaseModel):
    athlete_uuid: UUID
    task_id: int
    score: float = Field(..., ge=0, le=100)

    scores: dict[int, float]
    notes: str | None = None
    time: int


class SessionCompletionPayload(BaseModel):
    completions: list[TaskCompletionCreate]
    total_session_time: int


class EventItem(BaseModel):
    id: int
    title: str
    date: datetime
    type: Literal["course", "quick_session"]
    is_complete: bool
    course_id: int | None = None
    course_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionStatusUpdate(BaseModel):
    status: str


class CourseArchiveStatusUpdate(BaseModel):
    is_archived: bool
