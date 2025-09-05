# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Optional Prometheus instrumentation (safe if package missing)
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore
except Exception:  # pragma: no cover
    Instrumentator = None  # type: ignore

# Optional: Prometheus client for custom metrics (concurrency)
try:
    from prometheus_client import Gauge  # type: ignore
except Exception:  # pragma: no cover
    Gauge = None  # type: ignore

from src.api import api_router
from src.athlete import models as athlete_models  # noqa
from src.auth import models as auth_models  # noqa
from src.config import settings
from src.course import models as course_models  # noqa

app = FastAPI(title=settings.PROJECT_NAME)

# Instrument FastAPI with Prometheus metrics if available
if Instrumentator is not None:
    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )

# Minimal middleware to track in-flight requests (concurrency)
if Gauge is not None:
    from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

    INPROGRESS = Gauge("inprogress_requests", "In-progress HTTP requests")  # type: ignore

    class InflightMiddleware(BaseHTTPMiddleware):  # type: ignore
        async def dispatch(self, request, call_next):  # type: ignore
            INPROGRESS.inc()
            try:
                response = await call_next(request)
                return response
            finally:
                INPROGRESS.dec()

    # Add early so it wraps all following middlewares/routers
    app.add_middleware(InflightMiddleware)  # type: ignore

app.include_router(api_router)

origins = settings.CORS_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"msg": "Welcome to FastAPIApp!"}


@app.get("/health-check")
async def health_check():
    return {"status": "healthy"}
