# src/pagination.py
from fastapi import Query

def pagination_params(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
) -> dict:
    skip = (page - 1) * size
    return {"skip": skip, "limit": size}
