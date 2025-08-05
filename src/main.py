# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import api_router
from src.athlete import models as athlete_models  # noqa
from src.auth import models as auth_models  # noqa
from src.config import settings
from src.course import models as course_models  # noqa

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router)

origins = settings.CORS_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"msg": "Welcome to FastAPIApp!"}


@app.get("/health-check")
async def health_check():
    return {"status": "healthy"}
