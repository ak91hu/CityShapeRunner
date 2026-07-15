from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core import geometry as geom
from app.core.schemas import ArtworkDetail, ArtworkSummary, CityDetail, CitySuggestion, GeoPoint

_DATA_DIR = Path(os.environ.get("CSR_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))


@dataclass(frozen=True)
class City:
    id: str
    name: str
    country: str
    country_code: str
    osm_id: int | None
    osm_type: str | None
    bbox: tuple[float, float, float, float]  # west, south, east, north
    centroid: tuple[float, float]  # lat, lon
    has_river: bool
    bridge_count: int
    road_density: float
    city_affinity_tags: list[str] = field(default_factory=list)
    featured_artwork_ids: list[str] = field(default_factory=list)

    def to_suggestion(self) -> CitySuggestion:
        return CitySuggestion(
            id=self.id,
            name=self.name,
            country=self.country,
            country_code=self.country_code,
            osm_id=self.osm_id,
            bbox=list(self.bbox),
            centroid=GeoPoint(lat=self.centroid[0], lon=self.centroid[1]),
        )

    def to_detail(self) -> CityDetail:
        d = self.to_suggestion()
        return CityDetail(
            **d.model_dump(by_alias=True),
            road_density=self.road_density,
            has_river=self.has_river,
            bridge_count=self.bridge_count,
            featured_artwork_ids=list(self.featured_artwork_ids),
        )


@dataclass
class Artwork:
    id: str
    name: str
    category: str
    complexity: str
    recommended_min_km: float
    recommended_max_km: float
    aspect_ratio: float
    closed_path: bool
    default_sample_count: int
    symmetric: bool
    tags: list[str]
    city_affinity_tags: list[str]
    svg_text: str
    normalized: list[geom.Polyline]
    normalized_length: float

    def to_summary(self) -> ArtworkSummary:
        return ArtworkSummary(
            id=self.id,
            name=self.name,
            category=self.category,
            complexity=self.complexity,
            recommended_min_km=self.recommended_min_km,
            recommended_max_km=self.recommended_max_km,
            aspect_ratio=self.aspect_ratio,
            is_city_featured=False,
            preview_svg_url=f"/assets/shapes/{self.id}.svg",
            tags=list(self.tags),
            city_affinity_tags=list(self.city_affinity_tags),
        )

    def to_detail(self) -> ArtworkDetail:
        s = self.to_summary()
        return ArtworkDetail(
            **s.model_dump(by_alias=True),
            closed_path=self.closed_path,
            default_sample_count=self.default_sample_count,
            normalized_length=self.normalized_length,
            symmetric=self.symmetric,
        )

    def eligible_for(self, distance_km: float) -> bool:
        lo = self.recommended_min_km * 0.5
        hi = self.recommended_max_km * 2.0
        return lo <= distance_km <= hi


@lru_cache
def load_cities() -> tuple[City, ...]:
    raw = json.loads((_DATA_DIR / "seed" / "cities.json").read_text(encoding="utf-8"))
    out = []
    for c in raw["items"]:
        out.append(City(
            id=c["id"],
            name=c["name"],
            country=c["country"],
            country_code=c["country_code"],
            osm_id=c.get("osm_id"),
            osm_type=c.get("osm_type"),
            bbox=tuple(c["bbox"]),
            centroid=(c["centroid"]["lat"], c["centroid"]["lon"]),
            has_river=c.get("has_river", False),
            bridge_count=c.get("bridge_count", 0),
            road_density=c.get("road_density", 0.6),
            city_affinity_tags=c.get("city_affinity_tags", []),
            featured_artwork_ids=c.get("featured_artwork_ids", []),
        ))
    return tuple(out)


@lru_cache
def load_artworks() -> tuple[Artwork, ...]:
    raw = json.loads((_DATA_DIR / "seed" / "artworks.json").read_text(encoding="utf-8"))
    out = []
    for a in raw["items"]:
        svg_path = _DATA_DIR / "shapes" / f"{a['id']}.svg"
        svg_text = svg_path.read_text(encoding="utf-8")
        polylines = geom.parse_svg(svg_text)
        normalized = geom.normalize_polylines(polylines)
        length = geom.normalized_length(normalized)
        out.append(Artwork(
            id=a["id"], name=a["name"], category=a["category"], complexity=a["complexity"],
            recommended_min_km=a["recommended_min_km"], recommended_max_km=a["recommended_max_km"],
            aspect_ratio=a["aspect_ratio"], closed_path=a["closed_path"],
            default_sample_count=a["default_sample_count"], symmetric=a["symmetric"],
            tags=a.get("tags", []), city_affinity_tags=a.get("city_affinity_tags", []),
            svg_text=svg_text, normalized=normalized, normalized_length=length,
        ))
    return tuple(out)


def get_city(city_id: str) -> City | None:
    for c in load_cities():
        if c.id == city_id:
            return c
    return None


def list_all_cities() -> list[City]:
    return list(load_cities())


def search_cities(query: str, country: str | None = None, limit: int = 10) -> list[CitySuggestion]:
    q = query.strip().lower()
    if len(q) < 2:
        return []
    results = []
    for c in load_cities():
        if country and c.country_code.lower() != country.lower():
            continue
        if q in c.name.lower() or q in c.id.lower():
            results.append(c)
    results.sort(key=lambda c: (0 if c.name.lower().startswith(q) else 1, c.name))
    return [c.to_suggestion() for c in results[:limit]]


def get_artwork(artwork_id: str) -> Artwork | None:
    for a in load_artworks():
        if a.id == artwork_id:
            return a
    return None


def list_artworks(
    activity: str | None = None, distance_km: float | None = None, city: City | None = None
) -> list[ArtworkSummary]:
    out = []
    for a in load_artworks():
        if distance_km is not None and not a.eligible_for(distance_km):
            continue
        out.append(a.to_summary())
    return out


def artworks_by_ids(ids: list[str] | None) -> list[Artwork]:
    all_art = {a.id: a for a in load_artworks()}
    if ids is None:
        return list(all_art.values())
    return [all_art[i] for i in ids if i in all_art]
