"""Rank GPS-art templates against a city's routable street characteristics.

The recommender deliberately separates *template appeal* from *routeability*.
Every registered template is measured in unit space, then scored against the
curated city context, activity, and requested distance.  The best few shapes
are still routed and validated by the orchestrator; this module only chooses
which candidates are worth spending those comparatively expensive calls on.
"""

from __future__ import annotations

import cmath
import math
import re
from dataclasses import dataclass
from functools import cache, lru_cache

from . import geo, shape_library


@dataclass(frozen=True)
class ShapeRouteProfile:
    """Geometry-derived properties relevant to matching a street graph."""

    name: str
    path_count: int
    closed: bool
    unit_length: float
    sharp_turns: int
    turn_energy: float
    axis_order: float
    aspect_ratio: float
    complexity: float
    routeability: float

    @property
    def family(self) -> str:
        """A coarse family used to avoid testing three near-identical shapes."""
        detail = "simple" if self.complexity < 0.30 else (
            "moderate" if self.complexity < 0.68 else "detailed"
        )
        if self.path_count > 1:
            style = "disconnected"
        elif not self.closed:
            style = "open"
        elif self.axis_order >= 0.55:
            style = "orthogonal"
        elif self.sharp_turns <= 2:
            style = "smooth"
        else:
            style = "outline"
        return f"{detail}-{style}"


@dataclass(frozen=True)
class CityRouteProfile:
    """Normalized street-network traits inferred from curated city context."""

    city: str
    grid_order: float
    connectivity: float
    barrier_risk: float
    terrain_risk: float
    radial_order: float

    @property
    def detail_capacity(self) -> float:
        """How much shape detail the described street fabric can support."""
        value = (
            0.30
            + 0.34 * self.grid_order
            + 0.28 * self.connectivity
            - 0.22 * self.terrain_risk
            - 0.14 * self.barrier_risk
        )
        return _clamp(value, 0.18, 0.94)


@dataclass(frozen=True)
class ShapeRecommendation:
    name: str
    score: float
    reason: str
    shape: ShapeRouteProfile
    city: CityRouteProfile


# Curated numeric priors make Balaton recommendations explicit and stable.
# The prose contexts remain useful for planning and explanations, but parsing
# English keywords alone cannot distinguish a flat shore grid from a narrow
# volcanic peninsula with enough precision. Values are conservative starting
# priors; live snap/routing/validation still decides which route is usable.
_BALATON_LARGE_GRIDS = frozenset({"Keszthely", "Siófok"})
_BALATON_CONNECTED_GRIDS = frozenset({
    "Balatonboglár", "Balatonföldvár", "Balatonfüred", "Balatonlelle",
    "Balatonszabadi", "Balatonszemes", "Gyenesdiás", "Zamárdi",
})
_BALATON_FLAT_CORRIDORS = frozenset({
    "Balatonberény", "Balatonfenyves", "Balatonkeresztúr",
    "Balatonmáriafürdő", "Balatonőszöd", "Balatonszárszó",
    "Balatonszentgyörgy", "Balatonvilágos", "Szántód",
})
_BALATON_WESTERN_MIXED = frozenset({
    "Balatonederics", "Balatongyörök", "Fonyód", "Vonyarcvashegy",
})
_BALATON_SEVERELY_CONSTRAINED = frozenset({
    "Badacsonytomaj", "Badacsonytördemic", "Balatonrendes", "Örvényes",
    "Paloznak", "Szigliget", "Tihany",
})
_BALATON_HILLY_SHORE = frozenset({
    "Alsóörs", "Aszófő", "Ábrahámhegy", "Balatonakali",
    "Balatonakarattya", "Balatonalmádi", "Balatonfűzfő", "Balatonkenese",
    "Balatonszepezd", "Balatonudvari", "Csopak", "Kővágóörs",
    "Révfülöp", "Zánka",
})
_BALATON_INLAND_CORE = frozenset({"Balatonfőkajár"})


def _prior_group(
    cities: frozenset[str],
    values: tuple[float, float, float, float, float],
) -> dict[str, tuple[float, float, float, float, float]]:
    return {city.casefold(): values for city in cities}


BALATON_CITY_ROUTE_PRIORS = {
    **_prior_group(_BALATON_LARGE_GRIDS, (0.92, 0.90, 0.58, 0.12, 0.10)),
    **_prior_group(_BALATON_CONNECTED_GRIDS, (0.78, 0.80, 0.62, 0.25, 0.10)),
    **_prior_group(_BALATON_FLAT_CORRIDORS, (0.74, 0.67, 0.72, 0.15, 0.08)),
    **_prior_group(_BALATON_WESTERN_MIXED, (0.48, 0.55, 0.76, 0.58, 0.08)),
    **_prior_group(_BALATON_SEVERELY_CONSTRAINED, (0.30, 0.30, 0.84, 0.85, 0.05)),
    **_prior_group(_BALATON_HILLY_SHORE, (0.45, 0.44, 0.70, 0.66, 0.06)),
    **_prior_group(_BALATON_INLAND_CORE, (0.58, 0.55, 0.30, 0.22, 0.08)),
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _angle_delta(first: float, second: float) -> float:
    return (second - first + math.pi) % (2 * math.pi) - math.pi


@cache
def analyse_shape(name: str) -> ShapeRouteProfile:
    """Measure one registered template without relying on hand-written tiers."""
    generated = shape_library.get_shape(name)
    if generated is None:
        raise KeyError(f"unknown shape: {name}")
    _, paths, closed = generated
    normalized = geo.normalize_shape(paths)
    unit_length = geo.unit_perimeter(normalized)

    vectors: list[tuple[float, float]] = []
    turns: list[float] = []
    for path in normalized:
        local_angles: list[float] = []
        for start, end in zip(path, path[1:], strict=False):
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            if length <= 1e-9:
                continue
            angle = math.atan2(dy, dx)
            vectors.append((angle, length))
            local_angles.append(angle)
        turns.extend(
            abs(_angle_delta(first, second))
            for first, second in zip(local_angles, local_angles[1:], strict=False)
        )

    total_segment_length = sum(length for _, length in vectors) or 1.0
    # The magnitude is rotation-invariant: 1 means one dominant orthogonal
    # frame, while 0 means bearings spread evenly around the compass.
    axis_order = abs(
        sum(
            length * cmath.exp(4j * angle)
            for angle, length in vectors
        )
        / total_segment_length
    )
    sharp_turns = sum(turn >= math.radians(28) for turn in turns)
    turn_energy = sum(turns) / (2 * math.pi)

    points = [point for path in normalized for point in path]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    width = max(xs) - min(xs) if xs else 0.0
    height = max(ys) - min(ys) if ys else 0.0
    aspect_ratio = min(width, height) / max(width, height) if max(width, height) else 1.0

    path_count = len([path for path in normalized if len(path) >= 2])
    complexity = _clamp(
        0.055 * sharp_turns
        + 0.075 * max(0.0, turn_energy - 1.0)
        + 0.14 * max(0, path_count - 1)
        + 0.04 * max(0.0, unit_length - 3.2)
    )
    routeability = _clamp(
        1.0
        - 0.18 * max(0, path_count - 1)
        - 0.018 * max(0, sharp_turns - 6)
        - 0.045 * max(0.0, unit_length - 4.0)
        - (0.04 if not closed else 0.0)
    )
    return ShapeRouteProfile(
        name=name,
        path_count=path_count,
        closed=closed,
        unit_length=unit_length,
        sharp_turns=sharp_turns,
        turn_energy=turn_energy,
        axis_order=float(axis_order),
        aspect_ratio=aspect_ratio,
        complexity=complexity,
        routeability=routeability,
    )


def shape_catalog_profiles() -> dict[str, ShapeRouteProfile]:
    """Return measurements for every currently registered shape."""
    return {name: analyse_shape(name) for name in sorted(shape_library.SHAPES)}


@lru_cache(maxsize=512)
def analyse_city(city: str, map_context: str) -> CityRouteProfile:
    """Convert the curated prose profile into explicit scoring dimensions."""
    prior = BALATON_CITY_ROUTE_PRIORS.get(city.casefold().strip())
    if prior is not None:
        return CityRouteProfile(city, *prior)

    low = map_context.casefold()
    # Do not turn phrases such as "no major river" into a barrier signal.
    barriers_text = re.sub(
        r"\b(?:no|without)\s+(?:major\s+)?(?:river|lake|water|coast)\w*\b",
        "",
        low,
    )

    if any(
        phrase in low
        for phrase in (
            "excellent grid",
            "near-perfect grid",
            "regular street grid",
            "regular grid",
            "rectilinear grid",
            "strong grid",
        )
    ):
        grid_order = 0.94
    elif "grid" in low:
        grid_order = 0.74
    else:
        grid_order = 0.38

    if any(phrase in low for phrase in ("dense grid", "densest grid", "excellent")):
        connectivity = 0.94
    elif any(word in low for word in ("dense", "connected", "fine-grained")):
        connectivity = 0.82
    elif any(word in low for word in ("sparse", "limited", "disconnected")):
        connectivity = 0.28
    else:
        connectivity = 0.62

    barrier_hits = sum(
        word in barriers_text
        for word in ("river", "lake", "coast", "water", "canal", "island")
    )
    barrier_risk = _clamp(0.18 + 0.18 * barrier_hits)
    terrain_hits = sum(
        word in low
        for word in ("hilly", "hills", "mountain", "steep", "winding", "irregular")
    )
    terrain_risk = _clamp(0.10 + 0.15 * terrain_hits)
    radial_order = 0.90 if any(word in low for word in ("radial", "concentric")) else 0.12

    return CityRouteProfile(
        city=city,
        grid_order=grid_order,
        connectivity=connectivity,
        barrier_risk=barrier_risk,
        terrain_risk=terrain_risk,
        radial_order=radial_order,
    )


def _distance_capacity(sport: str, distance_km: float | None) -> float:
    if sport == "bike":
        distance = 24.0 if distance_km is None else distance_km
        return _clamp(0.28 + (distance - 10.0) / 75.0)
    distance = 10.0 if distance_km is None else distance_km
    return _clamp(0.20 + (distance - 3.0) / 32.0)


def _recommendation_reason(
    shape: ShapeRouteProfile,
    city: CityRouteProfile,
    sport: str,
) -> str:
    traits: list[str] = []
    if city.grid_order >= 0.72 and shape.axis_order >= 0.48:
        traits.append("aligns with the ordered street bearings")
    elif city.radial_order >= 0.70 and shape.aspect_ratio >= 0.72:
        traits.append("fits the radial street pattern")
    elif city.terrain_risk >= 0.40:
        traits.append("keeps the outline manageable on irregular terrain")
    elif city.barrier_risk >= 0.50:
        traits.append("uses a compact outline around major barriers")
    else:
        traits.append("matches the available street-network detail")

    if shape.path_count == 1:
        traits.append("stays on one continuous stroke")
    if shape.complexity < 0.34:
        traits.append("has few fragile turns")
    elif shape.complexity < 0.70:
        traits.append("balances detail with routeability")
    else:
        traits.append("uses the longer route to preserve extra detail")
    activity = "cycling" if sport == "bike" else "running"
    return f"For {activity}, it {traits[0]} and {traits[1]}."


def rank_shapes(
    city: str,
    map_context: str,
    sport: str,
    distance_km: float | None,
) -> list[ShapeRecommendation]:
    """Score the registry, returning a fresh list backed by a bounded cache."""
    clean_city = str(city).strip()[:100]
    clean_context = str(map_context).strip()[:4_000]
    clean_sport = "bike" if str(sport).casefold() == "bike" else "run"
    try:
        numeric_distance = float(distance_km) if distance_km is not None else None
    except (TypeError, ValueError):
        numeric_distance = None
    if numeric_distance is not None:
        numeric_distance = (
            round(min(300.0, max(1.0, numeric_distance)), 2)
            if math.isfinite(numeric_distance) and numeric_distance > 0
            else None
        )
    return list(
        _rank_shapes_cached(
            clean_city,
            clean_context,
            clean_sport,
            numeric_distance,
        )
    )


@lru_cache(maxsize=512)
def _rank_shapes_cached(
    city: str,
    map_context: str,
    sport: str,
    distance_km: float | None,
) -> tuple[ShapeRecommendation, ...]:
    """Immutable cached implementation for repeated planning passes."""
    city_profile = analyse_city(city, map_context)
    distance_capacity = _distance_capacity(sport, distance_km)
    supported_detail = min(city_profile.detail_capacity, distance_capacity)
    # Cycling graphs are often less direct than walkable graphs.  Longer bike
    # distances restore some detail capacity, but the same complexity is not
    # assumed to work equally well for both modes.
    if sport == "bike":
        supported_detail = max(0.18, supported_detail - 0.04)

    recommendations: list[ShapeRecommendation] = []
    for shape in shape_catalog_profiles().values():
        overshoot = max(0.0, shape.complexity - supported_detail)
        undershoot = max(0.0, supported_detail - shape.complexity)
        detail_fit = 1.0 - abs(shape.complexity - supported_detail)
        orientation_fit = (
            city_profile.grid_order * shape.axis_order
            + city_profile.radial_order * (1.0 - shape.axis_order) * shape.aspect_ratio
        )
        obstacle_fit = (
            (1.0 - city_profile.barrier_risk)
            + city_profile.barrier_risk * shape.aspect_ratio
        )
        terrain_fit = 1.0 - city_profile.terrain_risk * shape.complexity
        continuity = 1.0 if shape.path_count == 1 else max(0.0, 0.45 - 0.12 * (shape.path_count - 2))

        score = (
            0.22 * shape.routeability
            + 0.32 * detail_fit
            + 0.12 * orientation_fit
            + 0.10 * obstacle_fit
            + 0.10 * terrain_fit
            + 0.14 * continuity
            - 0.34 * overshoot
            - 0.08 * undershoot
        )
        recommendations.append(
            ShapeRecommendation(
                name=shape.name,
                score=score,
                reason=_recommendation_reason(shape, city_profile, sport),
                shape=shape,
                city=city_profile,
            )
        )

    return tuple(sorted(recommendations, key=lambda item: (-item.score, item.name)))


def recommend_shapes(
    city: str,
    map_context: str,
    sport: str,
    distance_km: float | None,
    *,
    limit: int = 3,
) -> list[ShapeRecommendation]:
    """Choose a strong but geometrically diverse set for live route testing."""
    if limit < 1:
        return []
    ranked = rank_shapes(city, map_context, sport, distance_km)
    selected: list[ShapeRecommendation] = []
    used_families: set[str] = set()

    # A disconnected drawing can require invisible transfer legs.  It is still
    # analysed and ranked, but automatic recommendations use continuous shapes
    # unless no such template exists.
    continuous = [item for item in ranked if item.shape.path_count == 1]
    pool = continuous or ranked
    for item in pool:
        if item.shape.family in used_families:
            continue
        selected.append(item)
        used_families.add(item.shape.family)
        if len(selected) == limit:
            return selected
    for item in pool:
        if item not in selected:
            selected.append(item)
        if len(selected) == limit:
            break
    return selected
