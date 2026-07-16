from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel

from app.core.schemas import RouteCreate, RouteDetail, SnapEditResponse
from app.services import ServiceError, export_service, route_service

router = APIRouter()

class SnapEditRequest(BaseModel):
    city_id: str
    activity: str
    lonlat: list[list[float]]
    difficulty: str = "normal"

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


@router.post("/routes/snap-edit", response_model=SnapEditResponse)
async def snap_edit(req: SnapEditRequest) -> SnapEditResponse:
    from app.graph_provider import city_or_fixture
    from app.core.snapping import snap_edit_route

    if not req.lonlat:
        return SnapEditResponse(lonlat=[], snapped=False, original_lonlat=[])

    result = city_or_fixture(req.city_id)
    if not result:
        return SnapEditResponse(
            lonlat=req.lonlat, snapped=False, original_lonlat=req.lonlat,
        )
    _city, graph, proj, _bbox = result
    diff = "medium" if req.difficulty == "normal" else req.difficulty
    filtered = graph.filter_for_profile(req.activity, diff)

    target = [(lat, lon) for lon, lat in req.lonlat]
    snap_result = snap_edit_route(target, filtered, proj, req.activity, req.difficulty)

    return SnapEditResponse(
        lonlat=[[lon, lat] for lat, lon in snap_result.route_lonlat],
        snapped=snap_result.snapped,
        warnings=snap_result.warnings,
        original_lonlat=[[lon, lat] for lat, lon in snap_result.original_lonlat],
        segments_failed=snap_result.segments_failed,
    )
