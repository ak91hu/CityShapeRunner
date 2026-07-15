from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

from app.core.units import Projector

type MetricPoint = tuple[float, float]
type GeoPoint = tuple[float, float]  # (lat, lon)


HARD_REJECT_HIGHWAY = {"motorway", "motorway_link"}


@dataclass
class Node:
    id: int
    x: float
    y: float
    lat: float
    lon: float
    degree: int = 0


@dataclass
class Edge:
    id: int
    from_id: int
    to_id: int
    osm_way_id: int = 0
    highway: str = "residential"
    surface: str = "asphalt"
    access: str | None = None
    bicycle: str | None = None
    foot: str | None = None
    oneway: str | None = None
    stairs: bool = False
    bridge: bool = False
    tunnel: bool = False
    length_m: float = 0.0
    geometry_xy: list[MetricPoint] = field(default_factory=list)
    geometry_lonlat: list[GeoPoint] = field(default_factory=list)
    base_weight: float = 0.0
    profile_weight: float = 0.0
    penalty_breakdown: dict[str, float] = field(default_factory=dict)
    rejected: bool = False


@dataclass
class RoadGraph:
    nodes: dict[int, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    adj: dict[int, list[tuple[int, Edge]]] = field(default_factory=dict)
    projector: Projector | None = None
    _edge_geoms: list[LineString] = field(default_factory=list)
    _tree: STRtree | None = None

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        self.adj.setdefault(node.id, [])

    def add_edge(self, edge: Edge, directed: bool = False) -> None:
        self.edges.append(edge)
        self.adj.setdefault(edge.from_id, []).append((edge.to_id, edge))
        if not directed:
            self.adj.setdefault(edge.to_id, []).append((edge.from_id, edge))
        self.nodes[edge.from_id].degree += 1
        self.nodes[edge.to_id].degree += 1

    def build_spatial_index(self) -> None:
        self._edge_geoms = [LineString(e.geometry_xy) for e in self.edges]
        self._tree = STRtree(self._edge_geoms)

    def filter_for_profile(self, activity: str, difficulty: str) -> "RoadGraph":
        """Return a view with profile weights set and rejected edges excluded from adj."""
        for e in self.edges:
            apply_profile_weight(e, activity, difficulty)
        filtered = RoadGraph(nodes=dict(self.nodes), projector=self.projector)
        filtered.edges = list(self.edges)
        for n in self.nodes.values():
            filtered.adj.setdefault(n.id, [])
        for e in self.edges:
            if e.rejected:
                continue
            filtered.adj[e.from_id].append((e.to_id, e))
            # Respect oneway for cycling; for running/walking treat as bidirectional.
            directed = activity == "cycling" and e.oneway == "yes"
            if not directed:
                filtered.adj[e.to_id].append((e.from_id, e))
        filtered.build_spatial_index()
        return filtered

    def nearest_edge(self, p: MetricPoint, tolerance: float) -> tuple[Edge | None, MetricPoint | None, float]:
        if self._tree is None:
            self.build_spatial_index()
        assert self._tree is not None
        query_box = box(p[0] - tolerance, p[1] - tolerance, p[0] + tolerance, p[1] + tolerance)
        idxs = list(self._tree.query(query_box))
        best: Edge | None = None
        best_pt: MetricPoint | None = None
        best_d = float("inf")
        pt = Point(p)
        for idx in idxs:
            edge = self.edges[idx]
            if edge.rejected:
                continue
            geom = self._edge_geoms[idx]
            d = geom.distance(pt)
            if d < best_d:
                best_d = d
                best = edge
                projected = geom.interpolate(geom.project(pt))
                best_pt = (projected.x, projected.y)
        if best is None or best_d > tolerance:
            return None, None, float("inf")
        return best, best_pt, best_d


# --------------------------------------------------------------------------- #
# Profile penalty tables (section 50)
# --------------------------------------------------------------------------- #

_HIGHWAY_MULT: dict[str, dict[str, float]] = {
    "running": {
        "footway": 0.85, "path": 0.85, "pedestrian": 0.85, "track": 1.10,
        "residential": 1.00, "living_street": 1.00, "service": 1.15,
        "tertiary": 1.35, "secondary": 2.00, "primary": 2.00, "cycleway": 1.10,
        "unclassified": 1.20, "steps": 1.10,
    },
    "cycling": {
        "cycleway": 0.70, "residential": 1.00, "living_street": 1.00,
        "tertiary": 1.30, "secondary": 2.50, "primary": 2.50, "service": 1.20,
        "footway": 3.00, "path": 3.00, "pedestrian": 3.00, "track": 1.20,
        "unclassified": 1.20,
    },
    "walking": {
        "footway": 0.80, "path": 0.80, "pedestrian": 0.80, "track": 1.00,
        "residential": 1.05, "living_street": 1.00, "service": 1.15,
        "tertiary": 1.50, "secondary": 2.25, "primary": 2.25, "cycleway": 1.10,
        "unclassified": 1.20, "steps": 0.95,
    },
}

_SURFACE_MULT: dict[str, float] = {
    "asphalt": 0.95, "paved": 0.95, "concrete": 0.95, "sett": 1.00,
    "gravel": 1.15, "ground": 1.15, "dirt": 1.20, "unpaved": 1.20,
    "sand": 1.40, "grass": 1.30,
}

_DIFFICULTY_PENALTY_FACTOR = {"easy": 1.25, "medium": 1.0, "hard": 0.8}


def _is_hard_rejected(edge: Edge, activity: str) -> bool:
    if edge.highway in HARD_REJECT_HIGHWAY:
        return True
    if edge.access == "no":
        return True
    if activity == "cycling" and (edge.bicycle == "no" or edge.highway == "steps"):
        return True
    if activity in ("running", "walking") and edge.foot == "no":
        return True
    return False


def apply_profile_weight(edge: Edge, activity: str, difficulty: str) -> None:
    """Compute profile_weight and rejected flag per section 20.3 / 50."""
    edge.rejected = _is_hard_rejected(edge, activity)
    edge.penalty_breakdown = {}
    if edge.rejected:
        edge.profile_weight = float("inf")
        return

    mult = _HIGHWAY_MULT[activity].get(edge.highway, 1.20)
    # cycling tertiary/secondary with a cycle lane gets a discount
    if activity == "cycling" and edge.highway in ("tertiary", "secondary", "primary"):
        if edge.bicycle in ("designated", "lane", "yes"):
            mult = min(mult, 1.10)
    # cycling footway/path with bicycle permission is usable
    if activity == "cycling" and edge.highway in ("footway", "path", "pedestrian"):
        if edge.bicycle in ("designated", "yes"):
            mult = 1.10

    surf = _SURFACE_MULT.get(edge.surface, 1.05)
    if activity == "cycling" and edge.surface in ("gravel", "ground", "dirt") and difficulty == "easy":
        surf = 2.00

    base = edge.length_m * mult * surf
    penalties = 0.0
    diff = _DIFFICULTY_PENALTY_FACTOR[difficulty]

    if edge.access == "private":
        penalties += 500.0 * diff
        edge.penalty_breakdown["private"] = 500.0 * diff
    if edge.access in ("unknown", None) and edge.highway in ("service",):
        penalties += 50.0
        edge.penalty_breakdown["unknown_access"] = 50.0
    if activity == "cycling" and edge.oneway == "yes":
        penalties += 1000.0
        edge.penalty_breakdown["oneway"] = 1000.0
    if edge.stairs and activity == "running":
        step_mult = 1.35 if difficulty == "easy" else 1.10
        base = edge.length_m * step_mult
        edge.penalty_breakdown["stairs"] = step_mult
    if edge.highway in ("primary", "secondary", "tertiary") and activity in ("running", "walking"):
        edge.penalty_breakdown["traffic"] = (mult - 1.0) * edge.length_m

    edge.base_weight = base
    edge.profile_weight = base + penalties


# --------------------------------------------------------------------------- #
# Fixture cities (section 58)
# --------------------------------------------------------------------------- #


@dataclass
class FixtureCity:
    id: str
    name: str
    centroid: GeoPoint
    bbox_metric: tuple[float, float, float, float]
    graph: RoadGraph
    has_river: bool = False
    bridge_count: int = 0
    featured_artwork_ids: list[str] = field(default_factory=list)


def _make_grid_graph(
    projector: Projector,
    cols: int,
    rows: int,
    spacing: float,
    origin: MetricPoint,
    highway: str = "residential",
    surface: str = "asphalt",
    access_override: dict[tuple[int, int, int, int], str] | None = None,
    steps_edges: set[tuple[int, int, int, int]] | None = None,
    bridge_edges: set[tuple[int, int, int, int]] | None = None,
    foot_override: dict[tuple[int, int, int, int], str] | None = None,
    bicycle_override: dict[tuple[int, int, int, int], str] | None = None,
) -> tuple[dict[tuple[int, int], int], list[Edge], dict[int, Node]]:
    """Build a regular grid of nodes/edges in metric coordinates."""
    ox, oy = origin
    node_ids: dict[tuple[int, int], int] = {}
    nodes: dict[int, Node] = {}
    nid = 0
    for j in range(rows):
        for i in range(cols):
            x = ox + i * spacing
            y = oy + j * spacing
            lat, lon = projector.to_wgs84(x, y)
            node_ids[(i, j)] = nid
            nodes[nid] = Node(id=nid, x=x, y=y, lat=lat, lon=lon)
            nid += 1

    edges: list[Edge] = []
    eid = 0

    def maybe_tag(i1, j1, i2, j2, edge: Edge) -> None:
        key = (i1, j1, i2, j2)
        if access_override and key in access_override:
            edge.access = access_override[key]
        if foot_override and key in foot_override:
            edge.foot = foot_override[key]
        if bicycle_override and key in bicycle_override:
            edge.bicycle = bicycle_override[key]
        if steps_edges and key in steps_edges:
            edge.stairs = True
            edge.highway = "steps"
        if bridge_edges and key in bridge_edges:
            edge.bridge = True

    for j in range(rows):
        for i in range(cols):
            a = node_ids[(i, j)]
            na = nodes[a]
            if i + 1 < cols:
                b = node_ids[(i + 1, j)]
                nb = nodes[b]
                length = math.hypot(nb.x - na.x, nb.y - na.y)
                e = Edge(
                    id=eid, from_id=a, to_id=b, highway=highway, surface=surface,
                    length_m=length,
                    geometry_xy=[(na.x, na.y), (nb.x, nb.y)],
                    geometry_lonlat=[(na.lat, na.lon), (nb.lat, nb.lon)],
                )
                maybe_tag(i, j, i + 1, j, e)
                edges.append(e)
                eid += 1
            if j + 1 < rows:
                b = node_ids[(i, j + 1)]
                nb = nodes[b]
                length = math.hypot(nb.x - na.x, nb.y - na.y)
                e = Edge(
                    id=eid, from_id=a, to_id=b, highway=highway, surface=surface,
                    length_m=length,
                    geometry_xy=[(na.x, na.y), (nb.x, nb.y)],
                    geometry_lonlat=[(na.lat, na.lon), (nb.lat, nb.lon)],
                )
                maybe_tag(i, j, i, j + 1, e)
                edges.append(e)
                eid += 1
    return node_ids, edges, nodes


def _assemble(projector: Projector, nodes: Iterable[Node], edges: Iterable[Edge]) -> RoadGraph:
    g = RoadGraph(projector=projector)
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e)
    g.build_spatial_index()
    return g


def build_mini_grid_city() -> FixtureCity:
    """10x10 residential grid, 100m spacing (section 58.1)."""
    centroid = (47.5, 19.04)
    proj = Projector.around(*centroid)
    spacing = 100.0
    cols = rows = 10
    _, edges, nodes = _make_grid_graph(proj, cols, rows, spacing, (0.0, 0.0))
    graph = _assemble(proj, nodes.values(), edges)
    return FixtureCity(
        id="mini-grid",
        name="Mini Grid City",
        centroid=centroid,
        bbox_metric=(0.0, 0.0, (cols - 1) * spacing, (rows - 1) * spacing),
        graph=graph,
        featured_artwork_ids=["heart", "star"],
    )


def build_river_city() -> FixtureCity:
    """Two dense grids separated by a river with two bridges (section 58.2)."""
    centroid = (47.5, 19.04)
    proj = Projector.around(*centroid)
    spacing = 100.0
    cols = rows = 6
    left_origin = (0.0, 0.0)
    right_origin = (700.0, 0.0)
    left_ids, left_edges, left_nodes = _make_grid_graph(proj, cols, rows, spacing, left_origin)
    right_ids, right_edges, right_nodes = _make_grid_graph(proj, cols, rows, spacing, right_origin)
    # Offset right-grid node IDs to avoid collision with left grid
    node_offset = max(left_nodes.keys()) + 1
    right_nodes = {nid + node_offset: node for nid, node in right_nodes.items()}
    for new_id, node in right_nodes.items():
        node.id = new_id
    for e in right_edges:
        e.from_id += node_offset
        e.to_id += node_offset
    nodes = {**left_nodes, **right_nodes}
    edges = list(left_edges) + list(right_edges)
    eid = max(e.id for e in edges) + 1 if edges else 0

    def connect(a_xy, b_xy):
        nonlocal eid
        # find nearest nodes to each xy
        def nearest(xy):
            best = min(nodes.values(), key=lambda n: (n.x - xy[0]) ** 2 + (n.y - xy[1]) ** 2)
            return best
        na = nearest(a_xy)
        nb = nearest(b_xy)
        length = math.hypot(nb.x - na.x, nb.y - na.y)
        e = Edge(
            id=eid, from_id=na.id, to_id=nb.id, highway="tertiary", surface="asphalt",
            length_m=length, bridge=True,
            geometry_xy=[(na.x, na.y), (nb.x, nb.y)],
            geometry_lonlat=[(na.lat, na.lon), (nb.lat, nb.lon)],
        )
        edges.append(e)
        eid += 1

    # two bridges across the river gap
    connect((500.0, 200.0), (700.0, 200.0))
    connect((500.0, 400.0), (700.0, 400.0))

    graph = _assemble(proj, nodes.values(), edges)
    return FixtureCity(
        id="river-city",
        name="River City",
        centroid=centroid,
        bbox_metric=(0.0, 0.0, 700.0 + (cols - 1) * spacing, (rows - 1) * spacing),
        graph=graph,
        has_river=True,
        bridge_count=2,
        featured_artwork_ids=["bridge", "danube-wave"],
    )


def build_restricted_city() -> FixtureCity:
    """Grid with access=no, private, and footway edges (section 58.3)."""
    centroid = (47.5, 19.04)
    proj = Projector.around(*centroid)
    spacing = 120.0
    cols = rows = 8
    access_override = {(2, 2, 3, 2): "no", (4, 4, 5, 4): "private"}
    foot_override = {(6, 0, 6, 1): "no"}
    bicycle_override = {(0, 6, 1, 6): "no"}
    steps_edges = {(3, 5, 3, 6)}
    _, edges, nodes = _make_grid_graph(
        proj, cols, rows, spacing, (0.0, 0.0),
        access_override=access_override,
        foot_override=foot_override,
        bicycle_override=bicycle_override,
        steps_edges=steps_edges,
    )
    graph = _assemble(proj, nodes.values(), edges)
    return FixtureCity(
        id="restricted-city",
        name="Restricted Area City",
        centroid=centroid,
        bbox_metric=(0.0, 0.0, (cols - 1) * spacing, (rows - 1) * spacing),
        graph=graph,
        featured_artwork_ids=["star", "crown"],
    )


FIXTURES: dict[str, FixtureCity] = {
    "mini-grid": build_mini_grid_city,
    "river-city": build_river_city,
    "restricted-city": build_restricted_city,
}


def get_fixture(fixture_id: str) -> FixtureCity | None:
    builder = FIXTURES.get(fixture_id)
    return builder() if builder else None


# --------------------------------------------------------------------------- #
# Synthetic city graph (deterministic MVP fallback for any seed city)
# --------------------------------------------------------------------------- #


def _lcg(seed: int):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state


def bbox_metric_for(projector: Projector, bbox_lonlat: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    west, south, east, north = bbox_lonlat
    x1, y1 = projector.to_metric(west, south)
    x2, y2 = projector.to_metric(east, north)
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def build_synthetic_graph_for_city(city, max_dim: int = 18) -> tuple[RoadGraph, Projector, tuple[float, float, float, float]]:
    """Build a deterministic grid graph covering the city bbox.

    This is the MVP road-graph provider used when no OSM extract is configured
    (spec section 65 step 17: the OSM adapter sits behind the same interface).
    Returns (graph, projector, bbox_metric).
    """
    proj = Projector.around(city.centroid[0], city.centroid[1])
    minx, miny, maxx, maxy = bbox_metric_for(proj, city.bbox)
    width = maxx - minx
    height = maxy - miny
    spacing = max(80.0, min(200.0, 160.0 - city.road_density * 60.0))
    # cap node count to keep MVP budget tractable
    max_cells = 56
    spacing = max(spacing, width / max_cells, height / max_cells)
    cols = int(width / spacing) + 1
    rows = int(height / spacing) + 1
    spacing_x = width / (cols - 1) if cols > 1 else width
    spacing_y = height / (rows - 1) if rows > 1 else height
    spacing = (spacing_x + spacing_y) / 2

    rng = _lcg(hash(city.id) & 0xFFFFFFFF)
    foot_override: dict[tuple[int, int, int, int], str] = {}
    bicycle_override: dict[tuple[int, int, int, int], str] = {}
    access_override: dict[tuple[int, int, int, int], str] = {}

    def maybe_tag(i1, j1, i2, j2):
        key = (i1, j1, i2, j2)
        r = next(rng)
        if r % 100 < 12:
            foot_override[key] = "yes"
        if r % 100 in (13, 14):
            bicycle_override[key] = "designated"
        if r % 1000 < 3:
            access_override[key] = "private"

    if city.has_river:
        # split grid into left/right with a river gap and 2 bridges
        left_cols = max(3, cols // 2)
        right_cols = cols - left_cols - 1
        left_spacing = spacing
        left_origin = (minx, miny)
        left_ids, left_edges, left_nodes = _make_grid_graph(
            proj, left_cols, rows, left_spacing, left_origin,
            foot_override=foot_override, bicycle_override=bicycle_override, access_override=access_override,
        )
        gap = spacing * 1.2
        right_origin = (minx + left_spacing * (left_cols - 1) + gap, miny)
        right_ids, right_edges, right_nodes = _make_grid_graph(
            proj, right_cols, rows, spacing, right_origin,
            foot_override=foot_override, bicycle_override=bicycle_override, access_override=access_override,
        )
        # Offset right-grid node IDs to avoid collision with left grid
        node_offset = max(left_nodes.keys()) + 1
        right_nodes = {nid + node_offset: node for nid, node in right_nodes.items()}
        for new_id, node in right_nodes.items():
            node.id = new_id
        for e in right_edges:
            e.from_id += node_offset
            e.to_id += node_offset
        nodes = {**left_nodes, **right_nodes}
        edges = list(left_edges) + list(right_edges)
        eid = max(e.id for e in edges) + 1 if edges else 0

        def nearest(xy):
            return min(nodes.values(), key=lambda n: (n.x - xy[0]) ** 2 + (n.y - xy[1]) ** 2)

        for bridge_y in (miny + height * 0.33, miny + height * 0.66):
            lx = minx + left_spacing * (left_cols - 1)
            na = nearest((lx, bridge_y))
            nb = nearest((right_origin[0], bridge_y))
            length = math.hypot(nb.x - na.x, nb.y - na.y)
            edges.append(Edge(
                id=eid, from_id=na.id, to_id=nb.id, highway="tertiary", surface="asphalt",
                length_m=length, bridge=True,
                geometry_xy=[(na.x, na.y), (nb.x, nb.y)],
                geometry_lonlat=[(na.lat, na.lon), (nb.lat, nb.lon)],
            ))
            eid += 1
        graph = _assemble(proj, nodes.values(), edges)
        return graph, proj, (minx, miny, maxx, maxy)

    _, edges, nodes = _make_grid_graph(
        proj, cols, rows, spacing, (minx, miny),
        foot_override=foot_override, bicycle_override=bicycle_override, access_override=access_override,
    )
    # apply deterministic tag sprinkling on the generated edges (post-hoc)
    rng2 = _lcg(hash(city.id + "tags") & 0xFFFFFFFF)
    for e in edges:
        r = next(rng2)
        if r % 100 < 12:
            e.highway = "footway"
        elif r % 100 in (13, 14):
            e.highway = "cycleway"
            e.bicycle = "designated"
        if r % 1000 < 3:
            e.access = "private"
    graph = _assemble(proj, nodes.values(), edges)
    return graph, proj, (minx, miny, maxx, maxy)

