# src/exceptions.py
from fastapi import HTTPException

NotFoundException = lambda detail="Not found": HTTPException(status_code=404, detail=detail)
