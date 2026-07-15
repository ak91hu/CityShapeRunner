from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.api.deps import request_id
from app.core.schemas import ArtworkDetail
from app.services import ServiceError, artwork_service

router = APIRouter()


@router.get("/artworks")
async def list_artworks(
    request: Request,
    activity: str | None = Query(None),
    distance_km: float | None = Query(None, alias="distanceKm"),
    city_id: str | None = Query(None, alias="cityId"),
) -> dict:
    items = artwork_service.list(activity=activity, distance_km=distance_km, city_id=city_id)
    return {
        "items": [a.model_dump(by_alias=True) for a in items],
        "meta": {"requestId": request_id(request), "cached": False},
    }


@router.get("/artworks/{artwork_id}", response_model=ArtworkDetail)
async def get_artwork(artwork_id: str) -> ArtworkDetail:
    art = artwork_service.get(artwork_id)
    if art is None:
        raise ServiceError("ARTWORK_NOT_FOUND", "Artwork not found.", status=404)
    return art.to_detail()


@router.get("/artworks/{artwork_id}/cities")
async def get_compatible_cities(
    artwork_id: str,
    activity: str = Query("running"),
    difficulty: str = Query("medium"),
) -> dict:
    """Return cities compatible with this artwork, with valid distance ranges."""
    from app.core.seed import get_artwork
    from app.core.shape_matching import compute_shape_city_compatibility

    art = get_artwork(artwork_id)
    if art is None:
        raise ServiceError("ARTWORK_NOT_FOUND", "Artwork not found.", status=404)

    compat = compute_shape_city_compatibility(art, activity=activity, difficulty=difficulty)
    return {
        "artworkId": artwork_id,
        "activity": activity,
        "difficulty": difficulty,
        "items": [
            {
                "cityId": c.city_id,
                "cityName": c.city_name,
                "fitScore": c.fit_score,
                "minKm": c.min_km,
                "maxKm": c.max_km,
                "recommendedKm": c.recommended_km,
                "isFeatured": c.is_featured,
            }
            for c in compat
        ],
    }


@router.get("/cities/{city_id}/artworks")
async def get_city_artworks(
    city_id: str,
    activity: str = Query("running"),
    difficulty: str = Query("medium"),
) -> dict:
    """Return shapes compatible with this city, ranked by fit score.

    Given a city, finds which artwork shapes can be placed there and at what
    distance ranges. Implements the algorithm's shape-city ranking (section 3).
    """
    from app.core.shape_matching import compute_city_shape_compatibility

    compat = compute_city_shape_compatibility(city_id, activity=activity, difficulty=difficulty)
    return {
        "cityId": city_id,
        "activity": activity,
        "difficulty": difficulty,
        "items": [
            {
                "artworkId": s.artwork_id,
                "artworkName": s.artwork_name,
                "category": s.category,
                "complexity": s.complexity,
                "previewSvgUrl": s.preview_svg_url,
                "fitScore": s.fit_score,
                "minKm": s.min_km,
                "maxKm": s.max_km,
                "recommendedKm": s.recommended_km,
                "isFeatured": s.is_featured,
            }
            for s in compat
        ],
    }
