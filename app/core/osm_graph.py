from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from shapely.geometry import LineString

from app.core.graph import Edge, Node, RoadGraph
from app.core.seed import City
from app.core.units import Projector, haversine_m

logger = logging.getLogger(__name__)


def _osm_cache_dir() -> Path:
    data_dir = Path(os.environ.get("CSR_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    cache = data_dir / "cache" / "osm"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _cache_path(city_id: str) -> Path:
    return _osm_cache_dir() / f"{city_id}.graphml"


def _cache_age(path: Path) -> timedelta:
    return datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)


def _first_tag_value(value, default: str | None = None) -> str | None:
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and value:
        return str(value[0])
    return str(value)


def _oneway_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _bool_tag(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("yes", "true", "1")


def _build_road_graph_from_osmnx(G_ox, projector: Projector) -> RoadGraph:
    """Convert an OSMnx MultiDiGraph to the app's RoadGraph."""
    graph = RoadGraph(projector=projector)

    for osm_nid, data in G_ox.nodes(data=True):
        lat = float(data["y"])
        lon = float(data["x"])
        x, y = projector.to_metric(lon, lat)
        graph.add_node(Node(id=osm_nid, x=x, y=y, lat=lat, lon=lon))

    eid = 0
    for u, v, _key, data in G_ox.edges(keys=True, data=True):
        geom_wgs = data.get("geometry")
        if geom_wgs is None:
            u_data = G_ox.nodes[u]
            v_data = G_ox.nodes[v]
            geom_wgs = LineString([(u_data["x"], u_data["y"]), (v_data["x"], v_data["y"])])

        coords_lonlat = list(geom_wgs.coords)
        coords_xy = [projector.to_metric(lon, lat) for lon, lat in coords_lonlat]

        highway = _first_tag_value(data.get("highway"), "residential")
        surface = _first_tag_value(data.get("surface"), "asphalt")
        access = _first_tag_value(data.get("access"))
        bicycle = _first_tag_value(data.get("bicycle"))
        foot = _first_tag_value(data.get("foot"))
        oneway = _oneway_value(data.get("oneway"))
        bridge = _bool_tag(data.get("bridge"))
        tunnel = _bool_tag(data.get("tunnel"))
        stairs = highway == "steps"

        osm_way_id = data.get("osmid", 0)
        if isinstance(osm_way_id, list):
            osm_way_id = osm_way_id[0]
        if not isinstance(osm_way_id, int):
            osm_way_id = 0

        length_m = float(data.get("length", 0.0) or 0.0)
        if length_m <= 0:
            length_m = sum(
                haversine_m(
                    (coords_lonlat[i][1], coords_lonlat[i][0]),
                    (coords_lonlat[i + 1][1], coords_lonlat[i + 1][0]),
                )
                for i in range(len(coords_lonlat) - 1)
            )

        edge = Edge(
            id=eid,
            from_id=u,
            to_id=v,
            osm_way_id=osm_way_id,
            highway=highway,
            surface=surface,
            access=access,
            bicycle=bicycle,
            foot=foot,
            oneway=oneway,
            stairs=stairs,
            bridge=bridge,
            tunnel=tunnel,
            length_m=length_m,
            geometry_xy=coords_xy,
            geometry_lonlat=[(lat, lon) for lon, lat in coords_lonlat],
        )
        graph.add_edge(edge, directed=False)
        eid += 1

    graph.build_spatial_index()
    return graph


def _bbox_metric_for_projector(
    projector: Projector, bbox_lonlat: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    west, south, east, north = bbox_lonlat
    x1, y1 = projector.to_metric(west, south)
    x2, y2 = projector.to_metric(east, north)
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def build_osm_graph_for_city(
    city: City, max_cache_age_days: int = 30
) -> tuple[RoadGraph, Projector, tuple[float, float, float, float]] | None:
    """Build a RoadGraph from OpenStreetMap data for a city.

    Uses OSMnx to download the street network, caches the OSMnx graph as
    GraphML in data/cache/osm/{city_id}.graphml, and converts it to the app's
    RoadGraph representation. Returns None if OSMnx is unavailable or the
    download/conversion fails, allowing callers to fall back to the synthetic
    grid graph.
    """
    try:
        import osmnx as ox
    except Exception as exc:
        logger.warning("OSMnx not available: %s", exc)
        return None

    cache_dir = _osm_cache_dir()
    cache_path = _cache_path(city.id)
    ox_raw_cache = cache_dir / "osmnx_raw"
    ox_raw_cache.mkdir(parents=True, exist_ok=True)

    projector = Projector.around(city.centroid[0], city.centroid[1])
    bbox_metric = _bbox_metric_for_projector(projector, city.bbox)

    G_ox = None

    if cache_path.exists() and _cache_age(cache_path).days <= max_cache_age_days:
        try:
            logger.info("Loading cached OSM graph for %s", city.id)
            G_ox = ox.io.load_graphml(cache_path)
        except Exception as exc:
            logger.warning("Failed to load cached OSM graph for %s: %s", city.id, exc)

    if G_ox is None:
        try:
            west, south, east, north = city.bbox
            logger.info("Downloading OSM graph for %s", city.id)
            ox.settings.use_cache = True
            ox.settings.cache_folder = str(ox_raw_cache)
            ox.settings.requests_timeout = 310
            ox.settings.overpass_settings = '[out:json][timeout:300]'
            ox.settings.overpass_url = "https://lz4.overpass-api.de/api/interpreter"
            ox.settings.overpass_rate_limit = False
            # OSMnx 2.x expects bbox=(left, bottom, right, top) which is (west, south, east, north).
            G_ox = ox.graph.graph_from_bbox(
                bbox=(west, south, east, north),
                network_type="all_public",
                simplify=True,
                retain_all=False,
            )
            ox.io.save_graphml(G_ox, cache_path)
        except Exception as exc:
            logger.warning("Failed to download OSM graph for %s: %s", city.id, exc)
            return None

    if G_ox is None or len(G_ox.nodes) == 0:
        logger.warning("Empty OSM graph for %s", city.id)
        return None

    try:
        graph = _build_road_graph_from_osmnx(G_ox, projector)
    except Exception as exc:
        logger.warning("Failed to convert OSM graph for %s: %s", city.id, exc)
        return None

    logger.info("OSM graph for %s: %d nodes, %d edges", city.id, len(graph.nodes), len(graph.edges))
    return graph, projector, bbox_metric
