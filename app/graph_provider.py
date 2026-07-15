from __future__ import annotations

import logging
from functools import lru_cache

from app.core.graph import RoadGraph, build_synthetic_graph_for_city, get_fixture
from app.core.osm_graph import build_osm_graph_for_city
from app.core.seed import City, get_city
from app.core.units import Projector

logger = logging.getLogger(__name__)

type BBoxMetric = tuple[float, float, float, float]


@lru_cache(maxsize=64)
def graph_for_city(city_id: str) -> tuple[RoadGraph, Projector, BBoxMetric] | None:
    """Return (graph, projector, bbox_metric) for a seed city.

    Tries to load a real OpenStreetMap road graph first; falls back to the
    deterministic synthetic grid if OSM data is unavailable or fails.
    """
    city = get_city(city_id)
    if city is None:
        return None

    osm_result = build_osm_graph_for_city(city)
    if osm_result is not None:
        return osm_result

    logger.warning("Failed to load real OSM data for %s. Falling back to synthetic grid.", city_id)
    return build_synthetic_graph_for_city(city)


def city_or_fixture(city_id: str) -> tuple[City, RoadGraph, Projector, BBoxMetric] | None:
    city = get_city(city_id)
    if city is not None:
        g = graph_for_city(city_id)
        if g is None:
            return None
        graph, proj, bbox = g
        return city, graph, proj, bbox
    fixture = get_fixture(city_id)
    if fixture is not None:
        from app.core.seed import City  # noqa
        fc = fixture
        # wrap fixture as a City-like object for the pipeline
        proxy = City(
            id=fc.id, name=fc.name, country="Hungary", country_code="HU",
            osm_id=None, osm_type=None, bbox=(fc.centroid[1] - 0.05, fc.centroid[0] - 0.05,
                                              fc.centroid[1] + 0.05, fc.centroid[0] + 0.05),
            centroid=fc.centroid, has_river=fc.has_river, bridge_count=fc.bridge_count,
            road_density=0.8, city_affinity_tags=[], featured_artwork_ids=fc.featured_artwork_ids,
        )
        return proxy, fc.graph, fc.graph.projector, fc.bbox_metric
    return None
