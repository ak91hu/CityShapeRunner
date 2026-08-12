"""SnapAgent: snap drawn waypoints to real roads via OpenRouteService."""

from __future__ import annotations

from shapely.geometry import LineString

from ..config import get_settings
from ..state import SnappedRoute, WorkflowState
from ..tools import geo, ors_client
from .base import BaseAgent


class SnapAgent(BaseAgent):
    name = "snap"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.route_draft is None or state.intent is None:
            raise RuntimeError("road snapping requires route draft and intent")
        # Clear stale snap errors from previous iterations. If this snap
        # succeeds, any prior "ORS routing failed" error is obsolete.
        state.errors = [e for e in state.errors if not e.startswith("snap:")]
        draft = state.route_draft
        waypoints = draft.waypoints
        state.candidate_count += 1
        if len(waypoints) < 2:
            state.errors.append("snap: fewer than 2 waypoints to snap")
            state.snapped = SnappedRoute(points=list(waypoints), total_distance_m=0.0, snapped=False)
            return state

        polyline, dist_m, snapped, readiness = ors_client.snap_route_detailed(
            waypoints, sport=state.intent.sport, closed=draft.closed
        )
        # Apply the refinement-controlled tolerance in local metre space, but
        # only on real road geometry. Degree-space tolerance over-simplifies
        # east/west detail increasingly toward the poles.
        tol = draft.simplify_tolerance
        if tol and tol > 0 and snapped and len(polyline) > 4:
            polyline = _simplify_road_geometry(polyline, tol)
        state.snapped = SnappedRoute(
            points=polyline,
            total_distance_m=dist_m,
            snapped=snapped,
            readiness=readiness,
        )
        if not snapped and get_settings().routing.ors_api_key:
            state.errors.append(
                "snap: ORS routing failed; route is straight-line, not on roads"
            )
        self._record(
            state,
            f"snapped={snapped} pts={len(polyline)} dist={dist_m/1000:.2f}km tol={tol:.1f}m",
        )
        return state


def _simplify_road_geometry(
    polyline: list[geo.LatLon],
    tolerance_m: float,
) -> list[geo.LatLon]:
    """Simplify routed geometry in metres without introducing a crossing."""

    if len(polyline) < 3 or tolerance_m <= 0:
        return list(polyline)
    center_lat = sum(lat for lat, _ in polyline) / len(polyline)
    center_lon = sum(lon for _, lon in polyline) / len(polyline)
    try:
        metre_points = [
            geo.latlon_to_unit(lat, lon, center_lat, center_lon, 1.0)
            for lat, lon in polyline
        ]
        original = LineString(metre_points)
        simplified = original.simplify(tolerance_m, preserve_topology=True)
        if original.is_simple and not simplified.is_simple:
            return list(polyline)
        simplified_points = [
            geo.unit_to_latlon(x, y, center_lat, center_lon, 1.0)
            for x, y in simplified.coords
        ]
    except (TypeError, ValueError):
        return list(polyline)
    if len(simplified_points) < 2:
        return list(polyline)
    simplified_points[0] = polyline[0]
    simplified_points[-1] = polyline[-1]
    return simplified_points
