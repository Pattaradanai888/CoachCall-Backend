# src/auth/models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from src.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True)  # Store the jti instead of the full token
    blacklisted_on = Column(DateTime, default=datetime.utcnow)