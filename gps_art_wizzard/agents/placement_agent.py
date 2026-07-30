"""PlacementAgent: project the unit-space shape onto a real city at the target distance."""

from __future__ import annotations

import math

from ..config import get_settings
from ..state import RouteDraft, WorkflowState
from ..tools import geo, geocoder
from .base import BaseAgent

_DEFAULT_TOLERANCE = 0.8  # metres; SnapAgent simplifies the road polyline to this

_NETWORK_DISTANCE_FACTORS = {
    "run": 1.45,
    "bike": 1.30,
}

_SHAPE_NETWORK_MULTIPLIERS = {
    # Curved and highly concave designs create more street detours than their
    # unit-space perimeter suggests. These empirical priors come from real ORS
    # results and only seed the first candidate; measured refinement remains
    # authoritative.
    "circle": 1.42,
    "flower": 1.42,
    "heart": 1.10,
    "star": 1.20,
    "butterfly": 1.18,
    "cat": 1.25,
    "dog": 1.25,
    "infinity": 1.30,
    "wave": 1.20,
    "crown": 1.45,
    "tree": 1.30,
    "text": 1.35,
}


def _estimated_route_unit_length(
    paths: list[geo.Path],
    sport: str,
    shape_name: str = "",
) -> float:
    """Estimate routed length, including transfers between separate strokes.

    The stitched polyline measures every visible stroke and every unavoidable
    transfer. A small, conservative network factor accounts for streets not
    following each ideal segment exactly. Later validation/refinement uses the
    measured routed distance, so this only needs to provide a stable first
    placement rather than guess shape complexity from point density.
    """
    stitched = geo.stitch_paths(paths)
    length = geo.unit_path_length(stitched)
    network_factor = _NETWORK_DISTANCE_FACTORS.get(sport, _NETWORK_DISTANCE_FACTORS["run"])
    shape_factor = _SHAPE_NETWORK_MULTIPLIERS.get(
        shape_name.casefold().split(":", maxsplit=1)[0],
        1.0,
    )
    return max(length * network_factor * shape_factor, 1e-9)


def _metres_to_dlat(m: float) -> float:
    return (m / geo.EARTH_R_M) * (180.0 / math.pi)


def _metres_to_dlon(m: float, lat: float) -> float:
    return (m / (geo.EARTH_R_M * math.cos(math.radians(lat)))) * (180.0 / math.pi)


class PlacementAgent(BaseAgent):
    name = "placement"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.shape is None or state.intent is None:
            raise RuntimeError("placement requires both shape and intent")

        if state.route_draft is None:
            state.route_draft = self._fresh_draft(state)
        # Always (re)compute waypoints from current shape + current draft params
        # so refinement tweaks (scale/rotation/offset) take effect cleanly.
        state.route_draft.waypoints = self.project(state.shape, state.route_draft)
        self._record(
            state,
            f"placed {len(state.route_draft.waypoints)} pts, "
            f"scale={state.route_draft.scale_m:.1f}m/u, rot={state.route_draft.rotation_deg:.0f}°",
        )
        return state

    # -- draft creation ----------------------------------------------------- #
    def _fresh_draft(self, state: WorkflowState) -> RouteDraft:
        if state.intent is None or state.shape is None:
            raise RuntimeError("placement requires both shape and intent")
        cfg = get_settings().workflow
        intent = state.intent
        city = intent.city or cfg.city_default
        plan = state.plan
        if (
            plan is not None
            and plan.center_lat is not None
            and plan.center_lon is not None
            and plan.city_bbox is not None
        ):
            center_lat = plan.center_lat
            center_lon = plan.center_lon
            city_bbox = plan.city_bbox
        else:
            geo_result = geocoder.geocode(city)
            center_lat = geo_result.lat
            center_lon = geo_result.lon
            city_bbox = geo_result.bbox
        estimated_unit_length = _estimated_route_unit_length(
            state.shape.paths,
            intent.sport,
            state.shape.name,
        )
        target_km = (
            intent.distance_km
            if intent.distance_km is not None
            else cfg.distance_defaults.get(intent.sport, 8.0)
        )
        target_m = target_km * 1000.0
        scale_m = target_m / estimated_unit_length

        # PlanningAgent may supply a map-aware hint; otherwise use the city
        # extent as a deterministic coarse orientation.
        # Use the plan's placement offsets to position in a good area (e.g.
        # east of the Danube in Budapest, away from water).
        rotation = plan.rotation_hint_deg if (plan and plan.rotation_hint_deg is not None) else (
            geo.bbox_long_axis_heading(city_bbox)
        )
        if plan and plan.scale_hint is not None:
            scale_m *= min(4.0, max(0.25, plan.scale_hint))

        lat_off = plan.lat_offset_m if plan else 0.0
        lon_off = plan.lon_offset_m if plan else 0.0

        return RouteDraft(
            center_lat=center_lat,
            center_lon=center_lon,
            scale_m=scale_m,
            rotation_deg=rotation,
            lat_offset_m=lat_off,
            lon_offset_m=lon_off,
            simplify_tolerance=_DEFAULT_TOLERANCE,
            waypoints=[],
            closed=state.shape.closed,
            target_distance_km=target_km,
        )

    # -- projection --------------------------------------------------------- #
    def project(self, shape, draft: RouteDraft):
        """Project one transformed shape draft into geographic coordinates."""
        rotated = geo.rotate_shape(shape.paths, math.radians(draft.rotation_deg))
        eff_lat = draft.center_lat + _metres_to_dlat(draft.lat_offset_m)
        eff_lon = draft.center_lon + _metres_to_dlon(draft.lon_offset_m, draft.center_lat)
        continuous_route = geo.stitch_paths(rotated)
        return geo.project_paths([continuous_route], eff_lat, eff_lon, draft.scale_m)

    # Kept as a compatibility alias for callers written before projection was
    # exposed as part of the placement/preflight interface.
    _project = project
