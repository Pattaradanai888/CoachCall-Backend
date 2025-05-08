# src/auth/exceptions.py
from fastapi import HTTPException

CredentialsException = HTTPException(status_code=401, detail="Could not validate credentials")
