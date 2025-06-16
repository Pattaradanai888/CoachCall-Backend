# scr/course/models.py
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Numeric, Table
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
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="courses")

    sessions = relationship("Session", back_populates="course", cascade="all, delete-orphan")
    attendees = relationship("Athlete", secondary='course_attendees', back_populates="courses")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    scheduled_date = Column(DateTime, nullable=False)

    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    course = relationship("Course", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    tasks = relationship("SessionTask", back_populates="session", cascade="all, delete-orphan",
                         order_by="SessionTask.sequence")
    attendance_records = relationship("SessionAttendee", back_populates="session", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="tasks")
    skill_weights = relationship("TaskSkillWeight", back_populates="task", cascade="all, delete-orphan")


class SessionTask(Base):
    __tablename__ = "session_tasks"
    session_id = Column(Integer, ForeignKey("sessions.id"), primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    sequence = Column(Integer, nullable=False)

    session = relationship("Session", back_populates="tasks")
    task = relationship("Task")


class TaskSkillWeight(Base):
    __tablename__ = "task_skill_weights"
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), primary_key=True)
    weight = Column(Numeric(3, 2), nullable=False)

    task = relationship("Task", back_populates="skill_weights")
    skill = relationship("Skill")


class SessionAttendee(Base):
    __tablename__ = "session_attendees"
    session_id = Column(Integer, ForeignKey("sessions.id"), primary_key=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), primary_key=True)
    was_present = Column(Boolean, default=False)

    session = relationship("Session", back_populates="attendance_records")
    athlete = relationship("Athlete")


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    score = Column(Numeric(4, 2), nullable=False)
    completed_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("Session")
    athlete = relationship("Athlete", back_populates="task_completions")
    task = relationship("Task")