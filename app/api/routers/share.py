from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import ShareView
from app.services import route_service

router = APIRouter()


@router.get("/share/{share_id}", response_model=ShareView)
async def get_share(share_id: str) -> ShareView:
    return route_service.get_share(share_id)
