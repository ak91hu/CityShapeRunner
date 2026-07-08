from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.generation import Candidate
from app.core.schemas import GenerationJobCreate, ScoreBreakdown

type GeoPoint = tuple[float, float]


@dataclass
class JobRecord:
    id: str
    request: GenerationJobCreate
    request_hash: str
    city_id: str
    status: str = "queued"
    progress_stage: str | None = None
    progress_percent: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class RouteRecord:
    id: str
    city_id: str
    city_name: str
    artwork_id: str
    artwork_name: str
    activity: str
    distance_km: float
    elevation_gain_m: float | None
    route_lonlat: list[GeoPoint]
    keypoint_lonlat: list[GeoPoint]
    target_lonlat: list[GeoPoint]
    scores: ScoreBreakdown
    warnings: list[str]
    visibility: str = "private"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class _Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.jobs: dict[str, JobRecord] = {}
        self.candidates: dict[str, Candidate] = {}
        self.candidate_city: dict[str, str] = {}
        self.routes: dict[str, RouteRecord] = {}
        self.shares: dict[str, str] = {}  # share_id -> route_id

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"


STORE = _Store()
