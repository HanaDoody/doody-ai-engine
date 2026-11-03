"""FastAPI entrypoint for the stateless Doody AI engine."""
from fastapi import FastAPI

from app.api import (
    routes_chat,
    routes_collection,
    routes_health,
    routes_mission,
    routes_onboarding,
    routes_report,
    routes_rhythm,
)

app = FastAPI(title="Doody AI Engine", version="0.7.0")

app.include_router(routes_health.router)
app.include_router(routes_onboarding.router)
app.include_router(routes_mission.router)
app.include_router(routes_rhythm.router)
app.include_router(routes_collection.router)
app.include_router(routes_chat.router)
app.include_router(routes_report.router)
