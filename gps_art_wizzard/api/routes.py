"""HTTP routes for the GPS art route planner."""

from __future__ import annotations

import logging
import math
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..agents.validation_agent import ValidationAgent
from ..config import get_settings
from ..logging_config import current_request_id
from ..orchestrator import generate
from ..state import Intent, RouteDraft, Shape, SnappedRoute, WorkflowState
from ..tools import geo, gpx_writer, ors_client

router = APIRouter()
log = logging.getLogger(__name__)


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["a heart run in Budapest, about 8km", "suggest a run in Debrecen, 10km"],
        description="Natural-language prompt describing the shape, city, sport, and optional target distance. "
        "Use 'suggest' to let AI pick the best shape for the city.",
    )

    @field_validator("prompt")
    @classmethod
    def normalise_prompt(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("prompt must not be blank")
        return cleaned


class GenerateResponse(BaseModel):
    request_id: str | None = None
    prompt: str
    intent: dict | None
    shape: dict | None
    suggested_shape: str | None = None
    requested_shape: str | None = None
    fit_decision: dict | None = None
    validation: dict | None
    distance_km: float | None
    snapped: bool | None
    iterations: int
    candidate_count: int = 0
    preflight_count: int = 0
    below_threshold: bool
    errors: list[str]
    history: list[dict]
    gpx: str | None
    tcx: str | None
    file_paths: dict
    points_preview: list[list[float]]
    ideal_preview: list[list[float]] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    preflight_candidates: list[dict] = Field(default_factory=list)


class EditedRouteRequest(BaseModel):
    control_points: list[list[float]] = Field(..., min_length=2, max_length=200)
    reference_points: list[list[float]] = Field(default_factory=list, max_length=500)
    sport: Literal["run", "bike"] = "run"
    closed: bool = False
    target_distance_km: float | None = Field(default=None, gt=0, le=500)
    name: str = Field(default="Edited GPS art route", min_length=1, max_length=120)

    @field_validator("control_points", "reference_points")
    @classmethod
    def validate_points(cls, value: list[list[float]]) -> list[list[float]]:
        cleaned: list[list[float]] = []
        for point in value:
            if not isinstance(point, list | tuple) or len(point) < 2:
                raise ValueError("each point must contain latitude and longitude")
            lat, lon = float(point[0]), float(point[1])
            if (
                not math.isfinite(lat)
                or not math.isfinite(lon)
                or not -90 <= lat <= 90
                or not -180 <= lon <= 180
            ):
                raise ValueError("route points must be finite latitude/longitude pairs")
            cleaned.append([lat, lon])
        return cleaned


class EditedRouteResponse(BaseModel):
    request_id: str | None = None
    points_preview: list[list[float]]
    distance_km: float
    snapped: bool
    below_recommended: bool
    validation: dict
    gpx: str
    tcx: str | None
    warnings: list[str] = Field(default_factory=list)


_MAX_PREVIEW_POINTS = 500


def _even_sample(points: list, n: int) -> list:
    """Evenly sample ``points`` to at most ``n`` entries, retaining endpoints."""
    if n < 1:
        raise ValueError("sample size must be positive")
    if len(points) <= n:
        return list(points)
    if n == 1:
        return [points[0]]
    indices = [round(index * (len(points) - 1) / (n - 1)) for index in range(n)]
    return [points[i] for i in indices]


def _state_to_response(state) -> dict:
    snapped = state.snapped
    export = state.export
    all_pts = snapped.points if snapped else []
    preview = [[p[0], p[1]] for p in _even_sample(all_pts, _MAX_PREVIEW_POINTS)]
    ideal_points = state.route_draft.waypoints if state.route_draft else []
    ideal_preview = [
        [point[0], point[1]]
        for point in _even_sample(ideal_points, _MAX_PREVIEW_POINTS)
    ]
    workflow = get_settings().workflow
    ranked_candidates = sorted(
        enumerate(state.candidates, start=1),
        key=lambda item: (
            item[1].validation.on_roads,
            item[1].validation.score,
            item[1].validation.shape_fidelity,
            item[1].validation.distance_fit,
        ),
        reverse=True,
    )
    candidates = []
    for original_index, candidate in ranked_candidates:
        validation = candidate.validation
        below_recommended = not (
            validation.on_roads
            and validation.score >= workflow.validation_score_threshold
            and validation.shape_fidelity >= workflow.min_shape_fidelity
            and validation.distance_fit >= 0.6
            and validation.closure >= 0.6
        )
        candidates.append(
            {
                "id": f"candidate-{original_index}",
                "shape_name": candidate.shape_name,
                "shape_source": candidate.shape_source,
                "points_preview": [
                    [point[0], point[1]]
                    for point in _even_sample(
                        candidate.points,
                        _MAX_PREVIEW_POINTS,
                    )
                ],
                "ideal_preview": [
                    [point[0], point[1]]
                    for point in _even_sample(
                        candidate.ideal_points,
                        _MAX_PREVIEW_POINTS,
                    )
                ],
                "distance_km": candidate.total_distance_m / 1000.0,
                "snapped": candidate.snapped,
                "closed": candidate.closed,
                "target_distance_km": candidate.target_distance_km,
                "validation": validation.__dict__,
                "below_recommended": below_recommended,
                "transform": {
                    "rotation_deg": candidate.rotation_deg,
                    "scale_m": candidate.scale_m,
                    "lat_offset_m": candidate.lat_offset_m,
                    "lon_offset_m": candidate.lon_offset_m,
                    "preflight_score": candidate.preflight_score,
                },
            }
        )
    return dict(
        request_id=state.request_id,
        prompt=state.prompt,
        intent=state.intent.__dict__ if state.intent else None,
        shape=(
            {"name": state.shape.name, "closed": state.shape.closed,
             "source": state.shape.source, "n_paths": len(state.shape.paths)}
            if state.shape else None
        ),
        suggested_shape=state.plan.suggested_shape if state.plan else None,
        requested_shape=state.requested_shape,
        fit_decision=state.fit_decision.__dict__ if state.fit_decision else None,
        validation=state.validation.__dict__ if state.validation else None,
        distance_km=(snapped.total_distance_m / 1000) if snapped else None,
        snapped=snapped.snapped if snapped else None,
        iterations=state.iterations,
        candidate_count=state.candidate_count,
        preflight_count=state.preflight_count,
        below_threshold=state.below_threshold,
        errors=state.errors,
        history=state.history,
        gpx=export.gpx if export else None,
        tcx=export.tcx if export else None,
        file_paths=export.file_paths if export else {},
        points_preview=preview,
        ideal_preview=ideal_preview,
        candidates=candidates,
        preflight_candidates=state.preflight_candidates,
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "GPS Art Wizard", "version": "0.1.0"}


@router.post("/generate", response_model=GenerateResponse)
def generate_route(req: GenerateRequest) -> dict:
    log.info(
        "Route generation requested",
        extra={
            "event": "generation.requested",
            "prompt_length": len(req.prompt),
        },
    )
    try:
        state = generate(req.prompt)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("route generation failed")
        raise HTTPException(
            status_code=500,
            detail="Route generation failed. Verify the routing and model-provider configuration.",
        ) from exc
    return _state_to_response(state)


@router.post("/edit-route", response_model=EditedRouteResponse)
def edit_route(req: EditedRouteRequest) -> dict:
    """Re-route user-edited control points and always return an editable GPX."""
    control_points = [(point[0], point[1]) for point in req.control_points]
    reference_points = [
        (point[0], point[1])
        for point in (req.reference_points or req.control_points)
    ]
    if geo.path_distance_m(control_points) > 1_000_000:
        raise HTTPException(
            status_code=422,
            detail="Edited route guides must stay within a 1,000 km total span.",
        )

    points, distance_m, snapped = ors_client.snap_route(
        control_points,
        sport=req.sport,
        closed=req.closed,
    )
    temporary = WorkflowState(
        prompt="manual route edit",
        request_id=current_request_id(),
        intent=Intent(
            shape="edited",
            text=None,
            city=None,
            sport=req.sport,
            distance_km=req.target_distance_km,
            style=None,
        ),
        shape=Shape(
            name="edited",
            paths=[[(0.0, 0.0), (1.0, 1.0)]],
            closed=req.closed,
            source="manual",
        ),
        route_draft=RouteDraft(
            center_lat=reference_points[0][0],
            center_lon=reference_points[0][1],
            scale_m=1.0,
            rotation_deg=0.0,
            lat_offset_m=0.0,
            lon_offset_m=0.0,
            simplify_tolerance=0.0,
            waypoints=reference_points,
            closed=req.closed,
            target_distance_km=req.target_distance_km,
        ),
        snapped=SnappedRoute(
            points=points,
            total_distance_m=distance_m,
            snapped=snapped,
        ),
    )
    ValidationAgent().run(temporary)
    if temporary.validation is None:
        raise HTTPException(status_code=500, detail="Edited route validation failed.")

    warnings = list(temporary.validation.issues)
    if not snapped:
        warnings.append(
            "Street routing was unavailable; this GPX follows the edited guide points."
        )
    gpx = gpx_writer.to_gpx(
        points,
        name=req.name,
        sport=req.sport,
        total_distance_m=distance_m,
    )
    try:
        tcx = gpx_writer.to_tcx(
            points,
            name=req.name,
            sport=req.sport,
            total_distance_m=distance_m,
        )
    except Exception:  # noqa: BLE001
        tcx = None
    log.info(
        "Edited route generated",
        extra={
            "event": "route.edit.completed",
            "sport": req.sport,
            "snapped": snapped,
            "point_count": len(points),
            "distance_km": round(distance_m / 1000.0, 3),
            "score": temporary.validation.score,
            "fidelity": temporary.validation.shape_fidelity,
        },
    )
    workflow = get_settings().workflow
    below_recommended = not (
        snapped
        and temporary.validation.score >= workflow.validation_score_threshold
        and temporary.validation.shape_fidelity >= workflow.min_shape_fidelity
        and temporary.validation.distance_fit >= 0.6
        and temporary.validation.closure >= 0.6
    )
    return {
        "request_id": temporary.request_id,
        "points_preview": [
            [point[0], point[1]]
            for point in _even_sample(points, _MAX_PREVIEW_POINTS)
        ],
        "distance_km": distance_m / 1000.0,
        "snapped": snapped,
        "below_recommended": below_recommended,
        "validation": temporary.validation.__dict__,
        "gpx": gpx,
        "tcx": tcx,
        "warnings": warnings,
    }
