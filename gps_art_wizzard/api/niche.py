"""Endpoints for field evidence, team murals, and time-aware readiness."""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..tools import geo, gpx_writer, ors_client, shape_similarity
from ..tools.experience_store import evidence_summary, record_completion
from ..tools.timed_readiness import time_readiness

router = APIRouter(tags=["GPS Art Intelligence"])


def _points(value: list[list[float]]) -> list[tuple[float, float]]:
    result = []
    for point in value:
        if len(point) < 2:
            raise ValueError("each point needs latitude and longitude")
        lat, lon = float(point[0]), float(point[1])
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("points must be finite latitude and longitude pairs")
        result.append((lat, lon))
    return result


class CompletionFeedbackRequest(BaseModel):
    shape_name: str = Field(min_length=1, max_length=80)
    sport: str = Field(pattern="^(run|bike)$")
    city: str | None = Field(default=None, max_length=100)
    planned_points: list[list[float]] = Field(min_length=2, max_length=1000)
    completed_points: list[list[float]] = Field(min_length=2, max_length=2000)
    blocked_segments: int = Field(default=0, ge=0, le=50)
    notes: list[str] = Field(default_factory=list, max_length=6)
    consent_to_learn: bool = False

    @field_validator("planned_points", "completed_points")
    @classmethod
    def validate_points(cls, value):
        _points(value)
        return value


@router.post("/completion-feedback")
def completion_feedback(request: CompletionFeedbackRequest) -> dict:
    planned = _points(request.planned_points)
    completed = _points(request.completed_points)
    likeness = shape_similarity.fidelity_between_routes(planned, completed, n=96)
    planned_km = geo.path_distance_m(planned) / 1000
    completed_km = geo.path_distance_m(completed) / 1000
    summary = {
        "shape_name": request.shape_name.strip(),
        "sport": request.sport,
        "city": request.city.strip() if request.city else None,
        "planned_km": round(planned_km, 3),
        "completed_km": round(completed_km, 3),
        "likeness": round(likeness, 4),
        "blocked_segments": request.blocked_segments,
        "notes": [" ".join(note.split())[:180] for note in request.notes if note.strip()],
    }
    if request.consent_to_learn:
        record_completion(summary)
    aggregate = evidence_summary(city=summary["city"], shape_name=summary["shape_name"])
    return {
        "completion": summary,
        "saved_for_learning": request.consent_to_learn,
        "evidence": aggregate,
        "message": (
            "Thanks. Your anonymous summary will improve future city recommendations."
            if request.consent_to_learn
            else "Your result was analysed locally and was not saved."
        ),
    }


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


def _split_by_distance(points: list[tuple[float, float]], participants: int) -> list[list[tuple[float, float]]]:
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
        raise HTTPException(status_code=422, detail="The route is too short to divide into that many mural sections.")
    sections = []
    for index, piece in enumerate(pieces, start=1):
        distance_m = geo.path_distance_m(piece)
        sections.append(
            {
                "id": f"mural-{index}",
                "label": f"Artist {index}",
                "points_preview": [[lat, lon] for lat, lon in piece],
                "distance_km": distance_m / 1000,
                "gpx": gpx_writer.to_gpx(piece, name=f"{request.name} - Artist {index}", sport=request.sport, total_distance_m=distance_m),
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


class RecognitionRepairRequest(BaseModel):
    reference_points: list[list[float]] = Field(min_length=4, max_length=500)
    sport: str = Field(default="run", pattern="^(run|bike)$")
    closed: bool = True
    name: str = Field(default="Refined GPS art", min_length=1, max_length=100)

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
    deduped = []
    for point in anchors:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if request.closed and deduped[0] != deduped[-1]:
        deduped.append(deduped[0])
    routed, distance_m, snapped, readiness = ors_client.snap_route_detailed(
        deduped,
        sport=request.sport,
        closed=request.closed,
    )
    fidelity = shape_similarity.fidelity_between_routes(guide, routed, n=96)
    return {
        "points_preview": [[lat, lon] for lat, lon in routed],
        "guide_points": [[lat, lon] for lat, lon in deduped],
        "distance_km": distance_m / 1000,
        "snapped": snapped,
        "recognition_score": fidelity,
        "readiness": asdict(readiness),
        "gpx": gpx_writer.to_gpx(routed, name=request.name, sport=request.sport, total_distance_m=distance_m),
        "message": "Re-routed from the shape's strongest visual anchors.",
    }
