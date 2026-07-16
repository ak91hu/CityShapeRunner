from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.stores import STORE  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset in-memory stores, rate limiter, graph cache and provider flags between tests."""
    STORE.jobs.clear()
    STORE.candidates.clear()
    STORE.candidate_city.clear()
    STORE.routes.clear()
    STORE.shares.clear()
    from app.services import rate_limiter
    rate_limiter._gen.clear()
    rate_limiter._gpx.clear()
    rate_limiter._search.clear()
    from app.config import get_settings
    get_settings.cache_clear()
    from app.graph_provider import graph_for_city
    graph_for_city.cache_clear()
    from app.core import shape_matching
    shape_matching._ORS_FAILED = False
    shape_matching._MAPBOX_FAILED = False
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def projector():
    from app.core.units import Projector
    return Projector.around(47.5, 19.04)


@pytest.fixture
def mini_grid():
    from app.core.graph import build_mini_grid_city
    return build_mini_grid_city()


@pytest.fixture
def river_city():
    from app.core.graph import build_river_city
    return build_river_city()


@pytest.fixture
def budapest():
    from app.core.seed import get_city
    return get_city("budapest")
