"""Seed the PostgreSQL database with cities and artworks from data/seed/*.

Run after migrations:  python scripts/seed_db.py
Requires CSR_DATABASE_URL pointing at a PostGIS-enabled database.
Idempotent: upserts by id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from geoalchemy2.elements import WKTElement

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> int:
    from app.db.session import db_available, session_scope
    from app.db.models import Artwork, City

    if not db_available():
        print("No PostGIS database available (set CSR_DATABASE_URL). Skipping seed.")
        return 0

    cities = json.loads((DATA / "seed" / "cities.json").read_text(encoding="utf-8"))["items"]
    arts = json.loads((DATA / "seed" / "artworks.json").read_text(encoding="utf-8"))["items"]

    with session_scope() as s:
        for c in cities:
            centroid = c["centroid"]
            wkt = f"POINT({centroid['lon']} {centroid['lat']})"
            existing = s.get(City, c["id"])
            if existing:
                existing.name = c["name"]
                existing.normalized_name = c["name"].lower()
                existing.country = c["country"]
                existing.country_code = c["country_code"]
                existing.centroid = WKTElement(wkt, srid=4326)
            else:
                s.add(City(
                    id=c["id"], name=c["name"], normalized_name=c["name"].lower(),
                    country=c["country"], country_code=c["country_code"],
                    osm_id=c.get("osm_id"), osm_type=c.get("osm_type"),
                    centroid=WKTElement(wkt, srid=4326),
                ))
        for a in arts:
            svg = (DATA / "shapes" / f"{a['id']}.svg").read_text(encoding="utf-8")
            existing = s.get(Artwork, a["id"])
            if existing:
                existing.name = a["name"]
                existing.category = a["category"]
                existing.complexity = a["complexity"]
                existing.svg_path = svg
                existing.aspect_ratio = a["aspect_ratio"]
                existing.recommended_min_km = a["recommended_min_km"]
                existing.recommended_max_km = a["recommended_max_km"]
            else:
                s.add(Artwork(
                    id=a["id"], name=a["name"], category=a["category"], complexity=a["complexity"],
                    svg_path=svg, aspect_ratio=a["aspect_ratio"],
                    recommended_min_km=a["recommended_min_km"], recommended_max_km=a["recommended_max_km"],
                    default_sample_count=a.get("default_sample_count", 200),
                ))
    print(f"Seeded {len(cities)} cities and {len(arts)} artworks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
