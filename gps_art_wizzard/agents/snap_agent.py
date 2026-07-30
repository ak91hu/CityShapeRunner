"""SnapAgent: snap drawn waypoints to real roads via OpenRouteService."""

from __future__ import annotations

from shapely.geometry import LineString

from ..config import get_settings
from ..state import SnappedRoute, WorkflowState
from ..tools import ors_client
from .base import BaseAgent

_M_PER_DEG = 111_320.0


class SnapAgent(BaseAgent):
    name = "snap"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.route_draft is None or state.intent is None:
            raise RuntimeError("road snapping requires route draft and intent")
        # Clear stale snap errors from previous iterations — if this snap
        # succeeds, any prior "ORS routing failed" error is obsolete.
        state.errors = [e for e in state.errors if not e.startswith("snap:")]
        draft = state.route_draft
        waypoints = draft.waypoints
        state.candidate_count += 1
        if len(waypoints) < 2:
            state.errors.append("snap: fewer than 2 waypoints to snap")
            state.snapped = SnappedRoute(points=list(waypoints), total_distance_m=0.0, snapped=False)
            return state

        polyline, dist_m, snapped = ors_client.snap_route(
            waypoints, sport=state.intent.sport, closed=draft.closed
        )
        # Apply the refinement-controlled simplify tolerance (metres -> degrees),
        # but only on real road geometry — the straight-line fallback is already
        # minimal and simplifying it just discards drawn vertices.
        tol = draft.simplify_tolerance
        if tol and tol > 0 and snapped and len(polyline) > 4:
            tol_deg = tol / _M_PER_DEG
            line = LineString([(lon, lat) for lat, lon in polyline])
            simplified = line.simplify(tol_deg, preserve_topology=False)
            poly = list(simplified.coords)
            if len(poly) >= 2:
                polyline = [(lat, lon) for lon, lat in poly]
        state.snapped = SnappedRoute(points=polyline, total_distance_m=dist_m, snapped=snapped)
        if not snapped and get_settings().routing.ors_api_key:
            state.errors.append(
                "snap: ORS routing failed; route is straight-line, not on roads"
            )
        self._record(
            state,
            f"snapped={snapped} pts={len(polyline)} dist={dist_m/1000:.2f}km tol={tol:.1f}m",
        )
        return state
