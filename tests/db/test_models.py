from __future__ import annotations

import uuid

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from app.db.models import Artwork, City, RouteCandidate, GenerationJob
from app.db.session import db_available, get_engine

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def db_ready():
    if not db_available():
        pytest.skip("PostgreSQL+PostGIS not available (set CSR_DATABASE_URL to a PostGIS-enabled database)")
    from app.db.models import Base
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "postgis"'))
        conn.commit()
    Base.metadata.create_all(engine)
    yield engine
    # leave tables for inspection; drop in CI if desired
    # Base.metadata.drop_all(engine)


def test_city_roundtrip(db_ready):
    from app.db.session import session_scope
    city_id = f"testcity_{uuid.uuid4().hex[:6]}"
    with session_scope() as s:  # type: Session
        s.add(City(
            id=city_id, name="Test City", normalized_name="test city",
            country="Hungary", country_code="HU",
            centroid=WKTElement("POINT(19.04 47.50)", srid=4326),
        ))
    with session_scope() as s:
        c = s.get(City, city_id)
        assert c is not None
        assert c.country_code == "HU"
    # cleanup
    with session_scope() as s:
        s.query(City).filter(City.id == city_id).delete()


def test_job_and_candidate_roundtrip(db_ready):
    from app.db.session import session_scope
    city_id = f"jobcity_{uuid.uuid4().hex[:6]}"
    job_id = uuid.uuid4()
    cand_id = f"cand_{uuid.uuid4().hex[:8]}"
    with session_scope() as s:
        s.add(City(id=city_id, name="Job City", normalized_name="job city",
                   country="Hungary", country_code="HU",
                   centroid=WKTElement("POINT(19.04 47.50)", srid=4326)))
        s.add(Artwork(id="heart", name="Heart", category="basic", complexity="easy",
                      svg_path="M0 0", aspect_ratio=1.0, recommended_min_km=5, recommended_max_km=15))
        s.add(GenerationJob(id=job_id, city_id=city_id, status="completed", activity="running",
                            target_distance_km=10.0, difficulty="medium", request_hash="hash123"))
        s.add(RouteCandidate(
            id=cand_id, job_id=job_id, artwork_id="heart", rank=1, status="ready",
            route_geometry=WKTElement("LINESTRING(19.04 47.50, 19.05 47.51)", srid=4326),
            distance_km=10.1, fit_score=0.9, shape_similarity_score=0.88,
        ))
    with session_scope() as s:
        cand = s.get(RouteCandidate, cand_id)
        assert cand is not None
        assert cand.fit_score == 0.9
        assert cand.job.city_id == city_id
    # cleanup
    with session_scope() as s:
        s.query(RouteCandidate).filter(RouteCandidate.id == cand_id).delete()
        s.query(GenerationJob).filter(GenerationJob.id == job_id).delete()
        s.query(Artwork).filter(Artwork.id == "heart").delete()
        s.query(City).filter(City.id == city_id).delete()
