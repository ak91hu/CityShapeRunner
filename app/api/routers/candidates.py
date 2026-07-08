from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.core.schemas import CandidateSummary
from app.services import candidate_geojson, generation_service

router = APIRouter()


@router.get("/candidates/{candidate_id}", response_model=CandidateSummary)
async def get_candidate(candidate_id: str) -> CandidateSummary:
    c = generation_service.get_candidate(candidate_id)
    from app.services import _candidate_summary
    return _candidate_summary(c)


@router.get("/candidates/{candidate_id}/geojson")
async def get_candidate_geojson(
    candidate_id: str,
    request: Request,
    layer: str | None = Query(None),
) -> dict:
    c = generation_service.get_candidate(candidate_id)
    return candidate_geojson(c, layer=layer)
