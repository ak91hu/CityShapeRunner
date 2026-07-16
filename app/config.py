from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CSR_", env_file=".env", extra="ignore")

    app_name: str = "CityShapeRunner"
    algorithm_version: str = "svg-first-1.0"
    public_web_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    database_url: str | None = None
    redis_url: str | None = None

    # Mapbox (snap-to-road + routing)
    mapbox_access_token: str = ""
    mapbox_base_url: str = "https://api.mapbox.com/directions/v5"

    # OpenRouteService
    ors_api_key: str = ""
    ors_base_url: str = "https://api.openrouteservice.org/v2/directions"

    # AI assistance (OpenCode Zen API)
    zen_api_key: str = ""
    zen_base_url: str = "https://api.opencode.ai"

    jwt_secret: str = "change-me"

    enable_elevation: bool = False
    enable_user_accounts: bool = False
    enable_ai_retry: bool = True
    # When False (default) the app uses fast deterministic synthetic grids.
    # Set True to attempt loading cached OSM extracts (much slower first load).
    use_osm_graphs: bool = False

    anon_generation_per_day: int = 10000
    anon_gpx_per_day: int = 10000
    city_search_per_min: int = 10000

    worker_timeout_seconds: int = 120
    max_candidate_transformations: int = 2000
    max_route_repairs: int = 200
    max_returned_candidates: int = 12

    # Algorithm tuning (from gps-art-shape-matching-algorithm.md)
    min_confidence: float = 0.65
    max_ai_retry_rounds: int = 2
    min_corridor_score: float = 0.30
    min_weighted_coverage: float = 0.40
    coarse_candidate_limit: int = 50
    medium_candidate_limit: int = 10
    final_candidate_limit: int = 5
    beam_width: int = 50
    candidates_per_sample: int = 5

    data_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

    @property
    def db_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def mapbox_available(self) -> bool:
        return bool(self.mapbox_access_token)

    @property
    def ai_available(self) -> bool:
        return bool(self.zen_api_key) and self.enable_ai_retry


@lru_cache
def get_settings() -> Settings:
    return Settings()
