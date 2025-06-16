# src/athlete/models.py
import datetime
import enum
import uuid
from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Boolean, Numeric,
    Enum as SQLAlchemyEnum, Table
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship
from src.database import Base

athlete_group_association = Table('athlete_group_association', Base.metadata,
                                  Column('athlete_id', Integer, ForeignKey('athletes.id'), primary_key=True),
                                  Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
                                  )
athlete_position_association = Table('athlete_position_association', Base.metadata,
                                     Column('athlete_id', Integer, ForeignKey('athletes.id'), primary_key=True),
                                     Column('position_id', Integer, ForeignKey('positions.id'), primary_key=True)
                                     )
course_attendees = Table('course_attendees', Base.metadata,
                         Column('course_id', Integer, ForeignKey('courses.id'), primary_key=True),
                         Column('athlete_id', Integer, ForeignKey('athletes.id'), primary_key=True)
                         )


class DominantHandEnum(str, enum.Enum):
    right = "Right"
    left = "Left"
    ambidextrous = "Ambidextrous"


class Athlete(Base):
    __tablename__ = "athletes"
    id = Column(Integer, primary_key=True)
    uuid = Column(PostgresUUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    preferred_name = Column(String(50), nullable=True)
    dominant_hand = Column(SQLAlchemyEnum(DominantHandEnum), nullable=True)
    age = Column(Integer)
    height = Column(Integer)
    weight = Column(Integer)
    date_of_birth = Column(DateTime, nullable=False)
    phone_number = Column(String(20))
    emergency_contact_name = Column(String(100))
    emergency_contact_phone = Column(String(20))
    profile_image_url = Column(String(500))
    notes = Column(String(1000))
    jersey_number = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="athletes")

    experience_level_id = Column(Integer, ForeignKey("experience_levels.id"), nullable=True)
    experience_level = relationship("ExperienceLevel", back_populates="athletes")

    groups = relationship("Group", secondary=athlete_group_association, back_populates="athletes")
    positions = relationship("Position", secondary=athlete_position_association, back_populates="athletes")
    courses = relationship("Course", secondary=course_attendees, back_populates="attendees")

    skill_levels = relationship("AthleteSkill", back_populates="athlete", cascade="all, delete-orphan")
    task_completions = relationship("TaskCompletion", back_populates="athlete", cascade="all, delete-orphan")


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="positions")
    athletes = relationship("Athlete", secondary=athlete_position_association, back_populates="positions")


class ExperienceLevel(Base):
    __tablename__ = "experience_levels"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="experience_levels")
    athletes = relationship("Athlete", back_populates="experience_level")


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="groups")
    athletes = relationship("Athlete", secondary=athlete_group_association, back_populates="groups")


class AthleteSkill(Base):
    __tablename__ = "athlete_skills"
    athlete_id = Column(Integer, ForeignKey("athletes.id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), primary_key=True)
    current_score = Column(Numeric(5, 2), nullable=False, default=0.0)

    athlete = relationship("Athlete", back_populates="skill_levels")
    skill = relationship("Skill")