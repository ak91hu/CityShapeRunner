from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _camel(alias: str) -> str:
    parts = alias.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_camel, extra="ignore")


class Activity(str, Enum):
    running = "running"
    cycling = "cycling"
    walking = "walking"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ExportMode(str, Enum):
    continuous = "continuous"
    connect_the_dots = "connect_the_dots"


class GeoPoint(CamelModel):
    lat: float
    lon: float


class CitySuggestion(CamelModel):
    id: str
    name: str
    country: str
    country_code: str = Field(alias="countryCode")
    osm_id: int | None = None
    bbox: list[float]  # [west, south, east, north]
    centroid: GeoPoint


class CityDetail(CitySuggestion):
    boundary_geojson: dict[str, Any] | None = None
    road_density: float | None = None
    has_river: bool | None = None
    bridge_count: int | None = None
    signature_artwork_ids: list[str] = Field(default_factory=list)


class ArtworkSummary(CamelModel):
    id: str
    name: str
    category: str
    complexity: str
    recommended_min_km: float
    recommended_max_km: float
    aspect_ratio: float
    is_city_signature: bool = False
    preview_svg_url: str
    tags: list[str] = Field(default_factory=list)
    city_affinity_tags: list[str] = Field(default_factory=list)


class ArtworkDetail(ArtworkSummary):
    closed_path: bool = True
    default_sample_count: int = 160
    normalized_length: float = 0.0
    symmetric: bool = False


class GenerationJobCreate(CamelModel):
    city_id: str = Field(min_length=1)
    activity: Activity
    target_distance_km: float = Field(ge=3, le=100)
    difficulty: Difficulty = Difficulty.medium
    artwork_ids: list[str] | None = None
    max_suggestions: int = Field(default=12, ge=1, le=20)
    export_modes: list[ExportMode] = Field(default_factory=lambda: [ExportMode.continuous])
    force: bool = False


class ScoreBreakdown(CamelModel):
    fit_score: float = Field(ge=0, le=1)
    shape_similarity_score: float = Field(ge=0, le=1)
    distance_accuracy_score: float = Field(ge=0, le=1)
    road_quality_score: float = Field(ge=0, le=1)
    continuity_score: float = Field(ge=0, le=1)
    elevation_score: float = Field(ge=0, le=1)


class CandidateSummary(CamelModel):
    candidate_id: str
    artwork_id: str
    artwork_name: str
    rank: int
    distance_km: float
    elevation_gain_m: float | None = None
    scores: ScoreBreakdown
    fit_score: float = Field(ge=0, le=1)
    shape_similarity_score: float = Field(ge=0, le=1)
    road_quality_score: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    preview_geo_json_url: str
    target_geo_json_url: str | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class GenerationJobCreated(CamelModel):
    job_id: str
    status: JobStatus


class GenerationJobStatus(CamelModel):
    job_id: str
    status: JobStatus
    progress_stage: str | None = None
    progress_percent: int = 0
    error_code: str | None = None
    error_message: str | None = None
    suggestions: list[CandidateSummary] = Field(default_factory=list)


class RouteCreate(CamelModel):
    candidate_id: str


class RouteDetail(CamelModel):
    route_id: str
    city_id: str
    artwork_id: str
    artwork_name: str
    activity: Activity
    distance_km: float
    elevation_gain_m: float | None = None
    scores: ScoreBreakdown
    warnings: list[str] = Field(default_factory=list)
    gpx_url: str
    gpx_connect_the_dots_url: str | None = None
    share_url: str | None = None
    visibility: str = "private"


class ShareCreate(CamelModel):
    route_id: str


class ShareView(CamelModel):
    share_id: str
    route_id: str
    city_name: str
    artwork_name: str
    activity: Activity
    distance_km: float
    geojson: dict[str, Any]


class ErrorEnvelope(CamelModel):
    code: str
    message: str
    fields: dict[str, str] | None = None
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorResponse(CamelModel):
    error: ErrorEnvelope


class ListMeta(CamelModel):
    request_id: str | None = None
    cached: bool = False


class ListResponse(CamelModel):
    items: list[Any]
    meta: ListMeta = Field(default_factory=ListMeta)


class HealthResponse(CamelModel):
    status: str
    version: str
    db: bool
