import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.health import router as health_router
from api.routes.projects import router as projects_router


DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_configured_origins = os.getenv("CORS_ALLOWED_ORIGINS")
ALLOWED_ORIGINS = (
    [origin.strip() for origin in _configured_origins.split(",") if origin.strip()]
    if _configured_origins
    else DEFAULT_DEV_ORIGINS
)

app = FastAPI(
    title="CinePilot AI API",
    version="0.1.0",
    description=(
        "API layer for the CinePilot AI production pipeline."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(projects_router)
