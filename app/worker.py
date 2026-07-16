from __future__ import annotations

import threading
import traceback
from datetime import datetime, timezone

from app.core import generation
from app.core.mapbox_client import snap_route_to_roads, compute_route_distance_km
from app.core.schemas import Activity, Difficulty
from app.core.seed import artworks_by_ids
from app.config import get_settings
from app.graph_provider import city_or_fixture
from app.stores import STORE, JobRecord

_ALGO_VERSION = "svg-first-1.0"


def _update(job: JobRecord, stage: str, percent: int) -> None:
    job.progress_stage = stage
    job.progress_percent = percent





def run_job(job_id: str) -> None:
    job = STORE.jobs.get(job_id)
    if job is None:
        return
    try:
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        _update(job, "loading_city", 5)

        resolved = city_or_fixture(job.city_id)
        if resolved is None:
            raise ValueError("CITY_NOT_FOUND")
        city, graph, projector, bbox = resolved

        _update(job, "building_indexes", 10)
        req = job.request
        artworks = artworks_by_ids(req.artwork_ids)
        if not artworks:
            raise ValueError("ARTWORK_NOT_FOUND")

        _update(job, "parsing_shapes", 15)

        def progress_callback(stage: str, percent: int) -> None:
            _update(job, stage, percent)

        candidates = generation.generate_suggestions(
            city=city,
            graph=graph,
            projector=projector,
            bbox_metric=bbox,
            artworks=artworks,
            activity=Activity(req.activity),
            target_distance_km=req.target_distance_km,
            difficulty=Difficulty(req.difficulty),
            max_suggestions=req.max_suggestions,
            algorithm_version=_ALGO_VERSION,
            max_transformations=24,
            progress_callback=progress_callback,
        )

        _update(job, "scoring", 85)
        if not candidates:
            raise ValueError("GENERATION_NO_VALID_CANDIDATE")

        _update(job, "storing_results", 90)

        _update(job, "storing_results", 96)
        for c in candidates:
            STORE.candidates[c.candidate_id] = c
            STORE.candidate_city[c.candidate_id] = city.id
            STORE.candidate_activity[c.candidate_id] = req.activity.value
            if not any(x.candidate_id == c.candidate_id for x in STORE.cached_candidates):
                STORE.cached_candidates.append(c)
        job.candidates = candidates[:req.max_suggestions]
        job.status = "completed"
        job.progress_stage = "completed"
        job.progress_percent = 100
        job.completed_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        code = str(exc).strip()
        if code in _USER_MESSAGES:
            job.error_code = code
            job.error_message = _USER_MESSAGES[code]
        else:
            job.error_code = "INTERNAL_ERROR"
            job.error_message = "Generation failed unexpectedly."
        job.completed_at = datetime.now(timezone.utc)
        traceback.print_exc()


_USER_MESSAGES = {
    "CITY_NOT_FOUND": "The selected city could not be found.",
    "ARTWORK_NOT_FOUND": "One or more selected artworks do not exist.",
    "GENERATION_NO_VALID_CANDIDATE": (
        "No recognizable route could be generated for this shape and distance. "
        "Try a longer distance, a simpler shape, or Running mode."
    ),
    "ROAD_GRAPH_UNAVAILABLE": "We could not load road data for this city right now. Please try again later.",
    "GENERATION_TIMEOUT": "Generation took too long and was cancelled. Please try a simpler request.",
}


def start_worker(job_id: str) -> None:
    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
