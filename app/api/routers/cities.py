from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.api.deps import client_ip, request_id
from app.core.schemas import CityDetail
from app.services import ServiceError, city_service, rate_limiter

router = APIRouter()


@router.get("/cities")
async def list_all_cities() -> dict:
    items = city_service.list_all()
    return {
        "items": [c.model_dump(by_alias=True) for c in items],
        "meta": {"count": len(items)},
    }


@router.get("/cities/search")
async def search(
    request: Request,
    q: str = Query(..., min_length=2),
    country: str | None = Query(None),
) -> dict:
    if not rate_limiter.allow_search(client_ip(request)):
        return {"items": [], "meta": {"requestId": request_id(request), "cached": False}}
    items = city_service.search(q, country)
    return {
        "items": [c.model_dump(by_alias=True) for c in items],
        "meta": {"requestId": request_id(request), "cached": False},
    }


@router.get("/cities/{city_id}", response_model=CityDetail)
async def get_city(city_id: str) -> CityDetail:
    city = city_service.get(city_id)
    if city is None:
        raise ServiceError("CITY_NOT_FOUND", "City not found.", status=404)
    return city
