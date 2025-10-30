# src/auth/models.py
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from src.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    skills = relationship("Skill", back_populates="user", cascade="all, delete-orphan")
    courses = relationship(
        "Course", back_populates="user", cascade="all, delete-orphan"
    )
    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    athletes = relationship(
        "Athlete", back_populates="user", cascade="all, delete-orphan"
    )

    positions = relationship(
        "Position", back_populates="user", cascade="all, delete-orphan"
    )
    # Experience levels are now global/hardcoded - no relationship needed
    groups = relationship("Group", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    display_name = Column(String, nullable=False)
    profile_image_url = Column(String, nullable=True)
    has_completed_onboarding = Column(Boolean, nullable=False, server_default="false")

    user = relationship("User", back_populates="profile")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    email = Column(String, primary_key=True)
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
