# src/main.py
import asyncio
from fastapi import FastAPI
from src.config import settings
from src.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router)

@app.get("/")
async def read_root():
    return {"msg": "Welcome to FastAPIApp!"}
