# src/rubrics/router.py
from fastapi import APIRouter, HTTPException, status

from .constants import get_all_skill_names, get_rubric
from .schemas import AvailableSkillsResponse, RubricResponse

router = APIRouter()


@router.get("/skills", response_model=AvailableSkillsResponse)
async def get_available_skills():
    return AvailableSkillsResponse(skills=get_all_skill_names())


@router.get("/{skill_name}", response_model=RubricResponse)
async def get_skill_rubric(skill_name: str):
    rubric = get_rubric(skill_name)

    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rubric not found for skill: {skill_name}",
        )

    return rubric
