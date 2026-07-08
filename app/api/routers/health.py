from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import HealthResponse
from app.db.session import db_available

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0", db=db_available())


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    return HealthResponse(status="ok" if db_available() else "degraded", version="1.0.0", db=db_available())
