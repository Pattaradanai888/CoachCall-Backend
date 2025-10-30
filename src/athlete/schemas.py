# src/athlete/schemas.py
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class GroupResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class PositionResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ExperienceLevelResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class AthleteSkillResponse(BaseModel):
    skill_id: int
    current_score: Decimal
    skill_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AthleteBase(BaseModel):
    name: str
    preferred_name: str | None = None
    age: int | None = None  # Will be calculated
    height: int | None = None
    weight: int | None = None
    dominant_hand: str | None = None  # Accept any string, will be validated
    date_of_birth: date
    phone_number: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    jersey_number: int | None = None

    # Foreign Keys and M2M IDs for creation/update
    experience_level_id: int | None = None
    group_ids: list[int] | None = []
    position_ids: list[int] | None = []

    @field_validator("dominant_hand", mode="before")
    @classmethod
    def normalize_dominant_hand(cls, v: str | None) -> str | None:
        """Convert frontend display values to database enum values (lowercase full words)"""
        if v is None:
            return None
        
        # Database enum expects: 'right', 'left', 'ambidextrous' (lowercase full words)
        mapping = {
            "Right": "right",
            "right": "right",
            "RIGHT": "right",
            "Left": "left",
            "left": "left",
            "LEFT": "left",
            "Ambidextrous": "ambidextrous",
            "ambidextrous": "ambidextrous",
            "AMBIDEXTROUS": "ambidextrous",
            "R": "right",  # Backwards compatibility
            "r": "right",
            "L": "left",
            "l": "left",
            "A": "ambidextrous",
            "a": "ambidextrous"
        }
        
        normalized = mapping.get(v)
        if normalized is None:
            raise ValueError(
                f"Invalid dominant_hand value: '{v}'. "
                "Must be 'Right', 'Left', or 'Ambidextrous'"
            )
        return normalized


class AthleteCreate(AthleteBase):
    @model_validator(mode="before")
    def calculate_age(cls, values):
        if "date_of_birth" in values and values["date_of_birth"]:
            today = date.today()
            birth_date = values["date_of_birth"]
            if isinstance(birth_date, str):
                birth_date = date.fromisoformat(birth_date)

            values["age"] = (
                today.year
                - birth_date.year
                - ((today.month, today.day) < (birth_date.month, birth_date.day))
            )
        return values


class AthleteUpdate(BaseModel):
    name: str | None = None
    preferred_name: str | None = None
    height: int | None = None
    weight: int | None = None
    dominant_hand: str | None = None  # Accept any string, will be validated
    date_of_birth: date | None = None
    phone_number: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    jersey_number: int | None = None
    experience_level_id: int | None = None
    group_ids: list[int] | None = None
    position_ids: list[int] | None = None

    @field_validator("dominant_hand", mode="before")
    @classmethod
    def normalize_dominant_hand(cls, v: str | None) -> str | None:
        """Convert frontend display values to database enum values (lowercase full words)"""
        if v is None:
            return None
        
        # Database enum expects: 'right', 'left', 'ambidextrous' (lowercase full words)
        # Frontend sends: 'Right', 'Left', 'Ambidextrous' (capitalized)
        mapping = {
            "Right": "right",
            "right": "right",
            "RIGHT": "right",
            "Left": "left",
            "left": "left",
            "LEFT": "left",
            "Ambidextrous": "ambidextrous",
            "ambidextrous": "ambidextrous",
            "AMBIDEXTROUS": "ambidextrous",
            "R": "right",  # Backwards compatibility
            "r": "right",
            "L": "left",
            "l": "left",
            "A": "ambidextrous",
            "a": "ambidextrous"
        }
        
        normalized = mapping.get(v)
        if normalized is None:
            raise ValueError(
                f"Invalid dominant_hand value: '{v}'. "
                "Must be 'Right', 'Left', or 'Ambidextrous'"
            )
        return normalized


class AthleteResponse(AthleteBase):
    uuid: UUID
    profile_image_url: str | None = None
    user_id: int

    experience_level: ExperienceLevelResponse | None = None
    groups: list[GroupResponse] = []
    positions: list[PositionResponse] = []
    skill_levels: list[AthleteSkillResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AthleteListResponse(BaseModel):
    uuid: UUID
    name: str
    age: int | None
    preferred_name: str | None
    position: str
    profile_image_url: str | None

    model_config = ConfigDict(from_attributes=True)


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupDeleteResponse(BaseModel):
    message: str
    deleted_group_id: int


class PositionCreate(BaseModel):
    name: str


class PositionDeleteResponse(BaseModel):
    message: str
    deleted_position_id: int


class AthleteSelectionResponse(BaseModel):
    uuid: UUID
    name: str
    profile_image_url: str | None = None
    positions: list[PositionResponse] = []
    age: int | None = None
    groups: list[GroupResponse] = []

    model_config = ConfigDict(from_attributes=True)
