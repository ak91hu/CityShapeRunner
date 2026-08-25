"""Endpoints for team murals, recognition repair, and time-aware readiness."""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..state import RoutePreferences
from ..tools import (
    accessibility_readiness,
    art_rescue,
    destination_catalog,
    geo,
    gpx_writer,
    lesson_pack,
    night_readiness,
    occasions,
    ors_client,
    route_landmarks,
    shape_similarity,
)
from ..tools.timed_readiness import time_readiness

router = APIRouter(tags=["GPS Art Intelligence"])


def _points(value: list[list[float]]) -> list[tuple[float, float]]:
    result = []
    for point in value:
        if len(point) < 2:
            raise ValueError("each point needs latitude and longitude")
        lat, lon = float(point[0]), float(point[1])
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError("points must be finite latitude and longitude pairs")
        result.append((lat, lon))
    return result


class MuralPlanRequest(BaseModel):
    points: list[list[float]] = Field(min_length=4, max_length=2_000)
    participants: int = Field(ge=2, le=24)
    name: str = Field(default="Community GPS mural", min_length=1, max_length=100)
    sport: str = Field(default="run", pattern="^(run|bike)$")

    @field_validator("points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


def _split_by_distance(
    points: list[tuple[float, float]], participants: int
) -> list[list[tuple[float, float]]]:
    total = geo.path_distance_m(points)
    if total <= 0:
        return []
    targets = [index * total / participants for index in range(participants + 1)]
    pieces, current, covered, target_index = [], [points[0]], 0.0, 1
    for start, end in zip(points, points[1:], strict=False):
        segment = geo.haversine(*start, *end)
        while target_index < len(targets) and covered + segment >= targets[target_index]:
            ratio = (targets[target_index] - covered) / segment if segment else 0.0
            cut = (start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio)
            current.append(cut)
            pieces.append(current)
            current = [cut]
            target_index += 1
        current.append(end)
        covered += segment
    if len(current) > 1:
        pieces.append(current)
    return [piece for piece in pieces if len(piece) > 1][:participants]


@router.post("/mural-plan")
def mural_plan(request: MuralPlanRequest) -> dict:
    points = _points(request.points)
    pieces = _split_by_distance(points, request.participants)
    if len(pieces) != request.participants:
        raise HTTPException(
            status_code=422,
            detail="The route is too short to divide into that many mural sections.",
        )
    sections = []
    for index, piece in enumerate(pieces, start=1):
        distance_m = geo.path_distance_m(piece)
        sections.append(
            {
                "id": f"mural-{index}",
                "label": f"Artist {index}",
                "points_preview": [[lat, lon] for lat, lon in piece],
                "distance_km": distance_m / 1000,
                "gpx": gpx_writer.to_gpx(
                    piece,
                    name=f"{request.name} - Artist {index}",
                    sport=request.sport,
                    total_distance_m=distance_m,
                ),
            }
        )
    return {
        "name": request.name,
        "participant_count": len(sections),
        "total_distance_km": geo.path_distance_m(points) / 1000,
        "sections": sections,
    }


class TimedReadinessRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    departure_at: datetime


@router.post("/timed-readiness")
def timed_readiness(request: TimedReadinessRequest) -> dict:
    when = request.departure_at
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return time_readiness(request.latitude, request.longitude, when)


class NightReadinessRequest(BaseModel):
    points: list[list[float]] = Field(min_length=2, max_length=5_000)

    @field_validator("points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/night-readiness")
def night_readiness_check(request: NightReadinessRequest) -> dict:
    """Street-lighting and traffic exposure evidence for one routed polyline."""

    return night_readiness.analyse(_points(request.points))


class RouteLandmarksRequest(BaseModel):
    points: list[list[float]] = Field(min_length=4, max_length=5_000)

    @field_validator("points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/route-landmarks")
def route_landmarks_along(request: RouteLandmarksRequest) -> dict:
    """Named sights within a short corridor of the planned route."""

    return route_landmarks.find_landmarks(_points(request.points))


class AccessibilityReadinessRequest(BaseModel):
    points: list[list[float]] = Field(min_length=2, max_length=5_000)

    @field_validator("points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/accessibility-readiness")
def accessibility_readiness_check(request: AccessibilityReadinessRequest) -> dict:
    """Wheelchair, steps, and surface evidence for one routed polyline."""

    return accessibility_readiness.analyse(_points(request.points))


class LessonPackRequest(BaseModel):
    reference_points: list[list[float]] = Field(min_length=3, max_length=500)
    closed: bool = True
    title: str = Field(default="My GPS drawing", min_length=1, max_length=80)
    shape_name: str = Field(default="drawing", min_length=1, max_length=60)

    @field_validator("reference_points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/lesson-pack")
def build_a_lesson_pack(request: LessonPackRequest) -> dict:
    """Classroom worksheet: lettered waypoints with bearings and distances."""

    return lesson_pack.build_lesson_pack(
        _points(request.reference_points),
        closed=request.closed,
        title=request.title,
        shape_name=request.shape_name,
    )


@router.get("/destinations")
def curated_destination_art() -> dict:
    """Curated city art picks for the composer's inspiration strip."""

    return {
        "destinations": [
            {
                "city": entry.city,
                "shape_prompt": entry.shape_prompt,
                "name": entry.name,
                "blurb": entry.blurb,
                "distance_km": entry.distance_km,
                "sport": entry.sport,
                "partner_ready": entry.partner_ready,
            }
            for entry in destination_catalog.CATALOGUE
        ]
    }


@router.get("/occasions")
def upcoming_occasions(
    days_ahead: int = Query(default=60, ge=1, le=365),
) -> dict:
    """Date-aware drawing suggestions for gifts, holidays, and national days."""

    return {
        "generated_on": date.today().isoformat(),
        "days_ahead": days_ahead,
        "occasions": occasions.upcoming_occasions(days_ahead=days_ahead),
    }


class InkproofRequest(BaseModel):
    points: list[list[float]] = Field(min_length=4, max_length=5_000)
    accuracy_m: float = Field(default=10.0, ge=3.0, le=50.0)

    @field_validator("points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/inkproof-analysis")
def inkproof(request: InkproofRequest) -> dict:
    """Forecast whether realistic GPS drift can erase fine drawing details."""

    return art_rescue.inkproof_analysis(_points(request.points), request.accuracy_m)


class RecordedGPX(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    gpx: str = Field(min_length=1, max_length=2_000_000)


class ArtRescueRequest(BaseModel):
    planned_points: list[list[float]] = Field(min_length=4, max_length=5_000)
    recordings: list[RecordedGPX] = Field(min_length=1, max_length=12)
    tolerance_m: float = Field(default=25.0, ge=5.0, le=100.0)
    name: str = Field(default="GPS art rescue", min_length=1, max_length=100)
    sport: str = Field(default="run", pattern="^(run|bike)$")

    @field_validator("planned_points")
    @classmethod
    def validate_planned_points(cls, value):
        _points(value)
        return value


@router.post("/art-rescue")
def rescue_recordings(request: ArtRescueRequest) -> dict:
    """Merge completed sessions without false strokes and isolate missing ink."""

    try:
        recordings = [
            art_rescue.parse_recording(recording.name, recording.gpx)
            for recording in request.recordings
        ]
        return art_rescue.rescue_analysis(
            _points(request.planned_points),
            recordings,
            tolerance_m=request.tolerance_m,
            name=request.name,
            sport=request.sport,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


class RecognitionRepairRequest(BaseModel):
    reference_points: list[list[float]] = Field(min_length=4, max_length=500)
    sport: str = Field(default="run", pattern="^(run|bike)$")
    closed: bool = True
    name: str = Field(default="Refined GPS art", min_length=1, max_length=100)
    route_preferences: dict[str, bool] = Field(default_factory=dict)

    @field_validator("reference_points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/recognition-repair")
def recognition_repair(request: RecognitionRepairRequest) -> dict:
    """Re-route a cue-preserving guide with fewer, stronger visual anchors."""

    guide = _points(request.reference_points)
    landmarks = shape_similarity.salient_route_landmarks(guide)
    anchors = [guide[0], *landmarks, guide[-1]]
    deduped: list[tuple[float, float]] = []
    for point in anchors:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if request.closed and deduped[0] != deduped[-1]:
        deduped.append(deduped[0])
    allowed_preference_keys = set(RoutePreferences.__dataclass_fields__)
    preference_values = {
        key: bool(value)
        for key, value in request.route_preferences.items()
        if key in allowed_preference_keys
    }
    route_preferences = (
        RoutePreferences(**preference_values) if any(preference_values.values()) else None
    )
    if route_preferences is None:
        routed, distance_m, snapped, readiness = ors_client.snap_route_detailed(
            deduped,
            sport=request.sport,
            closed=request.closed,
        )
    else:
        routed, distance_m, snapped, readiness = ors_client.snap_route_detailed(
            deduped,
            sport=request.sport,
            closed=request.closed,
            route_preferences=route_preferences,
        )
    fidelity = shape_similarity.fidelity_between_routes(guide, routed, n=96)
    return {
        "points_preview": [[lat, lon] for lat, lon in routed],
        "guide_points": [[lat, lon] for lat, lon in deduped],
        "distance_km": distance_m / 1000,
        "snapped": snapped,
        "recognition_score": fidelity,
        "readiness": asdict(readiness),
        "gpx": gpx_writer.to_gpx(
            routed, name=request.name, sport=request.sport, total_distance_m=distance_m
        ),
        "message": "Re-routed from the shape's strongest visual anchors.",
    }
