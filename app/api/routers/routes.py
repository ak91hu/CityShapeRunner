from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from app.core.schemas import RouteCreate, RouteDetail
from app.services import ServiceError, export_service, route_service

router = APIRouter()

GPX_MEDIA = "application/gpx+xml"


@router.post("/routes", response_model=RouteDetail, status_code=201)
async def create_route(req: RouteCreate) -> RouteDetail:
    return route_service.create_from_candidate(req.candidate_id)


@router.get("/routes/{route_id}", response_model=RouteDetail)
async def get_route(route_id: str) -> RouteDetail:
    return route_service.get_route(route_id)


@router.get("/routes/{route_id}/export/gpx")
async def export_gpx(
    route_id: str,
    request: Request,
    mode: str = Query("continuous"),
) -> Response:
    if mode not in ("continuous", "connect_the_dots"):
        raise ServiceError("VALIDATION_ERROR", "mode must be 'continuous' or 'connect_the_dots'.", status=422)
    rec = route_service.get_route_record(route_id)
    text, fname = export_service.gpx(rec, mode)
    return Response(
        content=text,
        media_type=GPX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/routes/{route_id}/share")
async def create_share(route_id: str) -> dict:
    share_id = route_service.create_share(route_id)
    return {"shareId": share_id, "shareUrl": f"/r/{share_id}"}
