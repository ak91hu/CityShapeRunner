from __future__ import annotations

import hashlib
import time
from collections import defaultdict

from app.config import get_settings
from app.core import gpx as gpx_mod
from app.core.generation import Candidate
from app.core.schemas import (
    Activity,
    CandidateSummary,
    CityDetail,
    CitySuggestion,
    GenerationJobCreate,
    GenerationJobStatus,
    RouteDetail,
    ShareView,
)
from app.core.seed import artworks_by_ids, get_artwork, get_city, list_artworks, search_cities
from app.stores import STORE, JobRecord, RouteRecord

ALGO_VERSION = "mvp-0.1"


# --------------------------------------------------------------------------- #
# City & artwork
# --------------------------------------------------------------------------- #


class CityService:
    def search(self, query: str, country: str | None = None, limit: int = 10) -> list[CitySuggestion]:
        return search_cities(query, country, limit)

    def get(self, city_id: str) -> CityDetail | None:
        city = get_city(city_id)
        return city.to_detail() if city else None

    def list_all(self) -> list[CityDetail]:
        from app.core.seed import list_all_cities
        return [c.to_detail() for c in list_all_cities()]


class ArtworkService:
    def list(self, activity: str | None = None, distance_km: float | None = None, city_id: str | None = None) -> list:
        city = get_city(city_id) if city_id else None
        return list_artworks(activity, distance_km, city)

    def get(self, artwork_id: str):
        return get_artwork(artwork_id)


# --------------------------------------------------------------------------- #
# Rate limiting (in-memory, per IP) - section 31
# --------------------------------------------------------------------------- #


class RateLimiter:
    def __init__(self) -> None:
        self._gen: dict[str, list[float]] = defaultdict(list)
        self._gpx: dict[str, list[float]] = defaultdict(list)
        self._search: dict[str, list[float]] = defaultdict(list)

    def _check(self, bucket: dict[str, list[float]], key: str, limit: int, window_s: int) -> bool:
        now = time.time()
        bucket[key] = [t for t in bucket[key] if now - t < window_s]
        if len(bucket[key]) >= limit:
            return False
        bucket[key].append(now)
        return True

    def allow_generation(self, ip: str) -> bool:
        s = get_settings()
        return self._check(self._gen, ip, s.anon_generation_per_day, 86400)

    def allow_gpx(self, ip: str) -> bool:
        s = get_settings()
        return self._check(self._gpx, ip, s.anon_gpx_per_day, 86400)

    def allow_search(self, ip: str) -> bool:
        s = get_settings()
        return self._check(self._search, ip, s.city_search_per_min, 60)


rate_limiter = RateLimiter()


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


def request_hash(req: GenerationJobCreate) -> str:
    art = ",".join(sorted(req.artwork_ids)) if req.artwork_ids else "auto"
    raw = f"{req.city_id}|{req.activity}|{req.target_distance_km}|{req.difficulty}|{art}|{ALGO_VERSION}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _candidate_summary(c: Candidate) -> CandidateSummary:
    return CandidateSummary(
        candidate_id=c.candidate_id,
        artwork_id=c.artwork_id,
        artwork_name=c.artwork_name,
        rank=c.rank,
        distance_km=round(c.distance_km, 2),
        elevation_gain_m=c.elevation_gain_m,
        scores=c.scores,
        fit_score=c.scores.fit_score,
        shape_similarity_score=c.scores.shape_similarity_score,
        road_quality_score=c.scores.road_quality_score,
        warnings=c.warnings,
        preview_geo_json_url=f"/api/candidates/{c.candidate_id}/geojson",
        target_geo_json_url=f"/api/candidates/{c.candidate_id}/geojson?layer=target",
        debug=c.debug,
    )


class GenerationService:
    def create_job(self, req: GenerationJobCreate, ip: str | None = None) -> tuple[str, str]:
        city = get_city(req.city_id)
        if city is None:
            raise ServiceError("CITY_NOT_FOUND", "City not found.")
        if req.artwork_ids:
            for aid in req.artwork_ids:
                if get_artwork(aid) is None:
                    raise ServiceError("ARTWORK_NOT_FOUND", f"Artwork '{aid}' not found.")
        else:
            if not artworks_by_ids(None):
                raise ServiceError("ARTWORK_NOT_FOUND", "Artwork catalog is empty.")
        if ip and not rate_limiter.allow_generation(ip):
            raise ServiceError(
                "RATE_LIMITED",
                "You reached today's free generation limit. Try again tomorrow or sign in for more.",
            )

        h = request_hash(req)
        # idempotency
        if not req.force:
            for j in STORE.jobs.values():
                if j.request_hash == h and j.status == "completed":
                    return j.id, j.status

        job_id = STORE.new_id("job")
        job = JobRecord(id=job_id, request=req, request_hash=h, city_id=req.city_id)
        STORE.jobs[job_id] = job
        from app.worker import start_worker
        start_worker(job_id)
        return job_id, job.status

    def get_job(self, job_id: str) -> GenerationJobStatus:
        job = STORE.jobs.get(job_id)
        if job is None:
            raise ServiceError("JOB_NOT_FOUND", "Job not found.")
        return GenerationJobStatus(
            job_id=job.id,
            status=job.status,
            progress_stage=job.progress_stage,
            progress_percent=job.progress_percent,
            error_code=job.error_code,
            error_message=job.error_message,
            suggestions=[_candidate_summary(c) for c in job.candidates],
        )

    def cancel_job(self, job_id: str) -> GenerationJobStatus:
        job = STORE.jobs.get(job_id)
        if job is None:
            raise ServiceError("JOB_NOT_FOUND", "Job not found.")
        if job.status in ("queued", "processing"):
            job.status = "cancelled"
            job.progress_stage = "cancelled"
        return self.get_job(job_id)

    def get_candidate(self, candidate_id: str) -> Candidate:
        c = STORE.candidates.get(candidate_id)
        if c is None:
            raise ServiceError("CANDIDATE_NOT_FOUND", "Candidate not found.")
        return c


# --------------------------------------------------------------------------- #
# Routes, export, share
# --------------------------------------------------------------------------- #


class RouteService:
    def create_from_candidate(self, candidate_id: str) -> RouteDetail:
        c = STORE.candidates.get(candidate_id)
        if c is None:
            raise ServiceError("CANDIDATE_NOT_FOUND", "Candidate not found.")
        city_id = STORE.candidate_city.get(candidate_id, "")
        city = get_city(city_id)
        route_id = STORE.new_id("route")
        rec = RouteRecord(
            id=route_id,
            city_id=city_id,
            city_name=city.name if city else city_id,
            artwork_id=c.artwork_id,
            artwork_name=c.artwork_name,
            activity=STORE.jobs and _activity_for_candidate(candidate_id),
            distance_km=c.distance_km,
            elevation_gain_m=c.elevation_gain_m,
            route_lonlat=c.route_lonlat,
            keypoint_lonlat=c.keypoint_lonlat,
            target_lonlat=c.target_lonlat,
            scores=c.scores,
            warnings=c.warnings,
        )
        STORE.routes[route_id] = rec
        return self._detail(rec)

    def get_route(self, route_id: str) -> RouteDetail:
        rec = STORE.routes.get(route_id)
        if rec is None:
            raise ServiceError("ROUTE_NOT_FOUND", "Route not found.")
        return self._detail(rec)

    def get_route_record(self, route_id: str) -> RouteRecord:
        rec = STORE.routes.get(route_id)
        if rec is None:
            raise ServiceError("ROUTE_NOT_FOUND", "Route not found.")
        return rec

    def create_share(self, route_id: str) -> str:
        if route_id not in STORE.routes:
            raise ServiceError("ROUTE_NOT_FOUND", "Route not found.")
        share_id = STORE.new_id("share")
        STORE.shares[share_id] = route_id
        return share_id

    def get_share(self, share_id: str) -> ShareView:
        route_id = STORE.shares.get(share_id)
        if route_id is None:
            raise ServiceError("SHARE_NOT_FOUND", "Share link not found.")
        rec = STORE.routes[route_id]
        return ShareView(
            share_id=share_id,
            route_id=route_id,
            city_name=rec.city_name,
            artwork_name=rec.artwork_name,
            activity=Activity(rec.activity),
            distance_km=round(rec.distance_km, 2),
            geojson=_route_geojson(rec),
        )

    def _detail(self, rec: RouteRecord) -> RouteDetail:
        settings = get_settings()
        base = settings.api_base_url
        return RouteDetail(
            route_id=rec.id,
            city_id=rec.city_id,
            artwork_id=rec.artwork_id,
            artwork_name=rec.artwork_name,
            activity=Activity(rec.activity),
            distance_km=round(rec.distance_km, 2),
            elevation_gain_m=rec.elevation_gain_m,
            scores=rec.scores,
            warnings=rec.warnings,
            gpx_url=f"{base}/api/routes/{rec.id}/export/gpx?mode=continuous",
            gpx_connect_the_dots_url=f"{base}/api/routes/{rec.id}/export/gpx?mode=connect_the_dots",
            share_url=f"/r/{self._share_for(rec.id)}",
        )

    def _share_for(self, route_id: str) -> str:
        for sid, rid in STORE.shares.items():
            if rid == route_id:
                return sid
        return ""


def _activity_for_candidate(candidate_id: str) -> str:
    for job in STORE.jobs.values():
        if any(c.candidate_id == candidate_id for c in job.candidates):
            return job.request.activity.value
    return "running"


class ExportService:
    def gpx(self, rec: RouteRecord, mode: str) -> tuple[str, str]:
        city = get_city(rec.city_id)
        city_name = city.name if city else rec.city_name
        name = f"{city_name} {rec.artwork_name} {int(round(rec.distance_km))}K {rec.activity.title()}"
        desc = (
            f"Generated by CityShapeRunner. Activity: {rec.activity}. "
            f"Distance: {rec.distance_km:.2f} km."
        )
        if mode == "connect_the_dots":
            text = gpx_mod.build_connect_the_dots_gpx(rec.keypoint_lonlat, name, desc)
            fname = gpx_mod.file_name(city_name, rec.artwork_name, rec.distance_km, rec.activity, "connect_the_dots")
        else:
            text = gpx_mod.build_continuous_gpx(rec.route_lonlat, name, desc)
            fname = gpx_mod.file_name(city_name, rec.artwork_name, rec.distance_km, rec.activity, "continuous")
        return text, fname


# --------------------------------------------------------------------------- #
# GeoJSON helpers
# --------------------------------------------------------------------------- #


def _route_geojson(rec: RouteRecord) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"kind": "route"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in rec.route_lonlat],
                },
            },
            {
                "type": "Feature",
                "properties": {"kind": "target_artwork"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in rec.target_lonlat],
                },
            },
            {
                "type": "Feature",
                "properties": {"kind": "keypoints"},
                "geometry": {
                    "type": "MultiPoint",
                    "coordinates": [[lon, lat] for lat, lon in rec.keypoint_lonlat],
                },
            },
        ],
    }


def candidate_geojson(c: Candidate, layer: str | None = None) -> dict:
    features = []
    if layer != "target":
        features.append({
            "type": "Feature",
            "properties": {"kind": "route"},
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in c.route_lonlat]},
        })
    if layer != "route":
        features.append({
            "type": "Feature",
            "properties": {"kind": "target_artwork"},
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in c.target_lonlat]},
        })
    if not layer:
        features.append({
            "type": "Feature",
            "properties": {"kind": "keypoints"},
            "geometry": {"type": "MultiPoint", "coordinates": [[lon, lat] for lat, lon in c.keypoint_lonlat]},
        })
    return {"type": "FeatureCollection", "features": features}


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, fields: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields


city_service = CityService()
artwork_service = ArtworkService()
generation_service = GenerationService()
route_service = RouteService()
export_service = ExportService()
