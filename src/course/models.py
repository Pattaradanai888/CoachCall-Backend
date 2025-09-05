# src/course/models.py
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.database import Base


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="skills")


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    cover_image_url = Column(String, nullable=True)
    is_archived = Column(Boolean, default=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="courses")

    sessions = relationship(
        "Session", back_populates="course", cascade="all, delete-orphan"
    )
    attendees = relationship(
        "Athlete", secondary="course_attendees", back_populates="courses"
    )


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="Pending")
    is_template = Column(Boolean, default=False)
    total_session_time_seconds = Column(Integer, nullable=True)

    course_id = Column(
        Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    course = relationship("Course", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    tasks = relationship(
        "SessionTask",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionTask.sequence",
    )
    attendance_records = relationship(
        "SessionAttendee", back_populates="session", cascade="all, delete-orphan"
    )
    completions = relationship(
        "TaskCompletion", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sessions_status_scheduled_date", "status", "scheduled_date"),
    )

    @property
    def total_duration_minutes(self) -> int:
        if not self.tasks:
            return 0
        return sum(
            st.task.duration_minutes
            for st in self.tasks
            if st.task and st.task.duration_minutes
        )


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="tasks")
    skill_weights = relationship(
        "TaskSkillWeight", back_populates="task", cascade="all, delete-orphan"
    )


class SessionTask(Base):
    __tablename__ = "session_tasks"
    session_id = Column(Integer, ForeignKey("sessions.id"), primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    sequence = Column(Integer, nullable=False)

    session = relationship("Session", back_populates="tasks")
    task = relationship("Task", cascade="all, delete-orphan", single_parent=True)


class TaskSkillWeight(Base):
    __tablename__ = "task_skill_weights"
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), primary_key=True)
    weight = Column(Numeric(3, 2), nullable=False)

    task = relationship("Task", back_populates="skill_weights")
    skill = relationship("Skill")

    @property
    def skill_name(self) -> str:
        return self.skill.name


class SessionAttendee(Base):
    __tablename__ = "session_attendees"
    session_id = Column(Integer, ForeignKey("sessions.id"), primary_key=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), primary_key=True)
    was_present = Column(Boolean, default=False)

    session = relationship("Session", back_populates="attendance_records")
    athlete = relationship("Athlete", back_populates="session_attendees")


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)

    final_score = Column(Numeric(5, 2), nullable=False)
    scores_breakdown = Column(JSONB, nullable=True)
    notes = Column(String, nullable=True)
    time_seconds = Column(Integer, nullable=True)

    completed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("Session", back_populates="completions")
    athlete = relationship("Athlete", back_populates="task_completions")
    task = relationship("Task")

    @property
    def athlete_uuid(self) -> uuid.UUID:
        return self.athlete.uuid
