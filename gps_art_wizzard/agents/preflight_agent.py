"""PreflightAgent: cheaply rank shape placements before full routing.

The expensive Directions endpoint is a poor search primitive. This agent
generates a broad set of scale/rotation/translation candidates, batch-snaps
their sparse guide points to the road graph in one request, and keeps only the
best placements for measured Directions routing.
"""

from __future__ import annotations

import copy
import math

from ..config import get_settings
from ..state import RouteDraft, WorkflowState
from ..tools import geo, ors_client
from .base import BaseAgent
from .placement_agent import PlacementAgent


class PreflightAgent(BaseAgent):
    name = "preflight"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.route_draft is None or state.shape is None or state.intent is None:
            raise RuntimeError("preflight requires route draft, shape, and intent")
        state.placement_candidates = []
        workflow = get_settings().workflow
        if not workflow.preflight_enabled:
            self._record(state, "preflight disabled")
            return state

        drafts = self._candidate_drafts(state)
        results = ors_client.preflight_route_candidates(
            [draft.waypoints for draft in drafts],
            sport=state.intent.sport,
            closed=state.shape.closed,
            max_guide_points=workflow.preflight_guide_points,
        )
        if results is None:
            self._record(state, "preflight unavailable; using deterministic placement")
            return state
        state.preflight_count += len(drafts)
        if not results:
            self._record(state, "preflight found no snappable placement")
            return state

        shortlist_size = min(
            max(1, workflow.preflight_shortlist),
            len(results),
        )
        for result in results:
            if result.candidate_index >= len(drafts):
                continue
            draft = drafts[result.candidate_index]
            state.preflight_candidates.append(
                {
                    "shape": state.shape.name,
                    "score": result.score,
                    "snap_coverage": result.snap_coverage,
                    "snap_distance_m": result.mean_snap_distance_m,
                    "shape_proxy": result.shape_fidelity,
                    "turning_proxy": result.turning_similarity,
                    "landmark_proxy": result.landmark_similarity,
                    "length_proxy": result.length_similarity,
                    "route_length_ratio": result.route_length_ratio,
                    "rotation_deg": draft.rotation_deg,
                    "scale_m": draft.scale_m,
                    "lat_offset_m": draft.lat_offset_m,
                    "lon_offset_m": draft.lon_offset_m,
                }
            )
        shortlisted_results = self._diverse_shortlist(
            results,
            drafts,
            shortlist_size,
        )
        ranked_drafts: list[RouteDraft] = []
        for rank, result in enumerate(shortlisted_results, start=1):
            if result.candidate_index >= len(drafts):
                continue
            draft = copy.deepcopy(drafts[result.candidate_index])
            draft.preflight_score = result.score
            draft.preflight_coverage = result.snap_coverage
            draft.preflight_snap_distance_m = result.mean_snap_distance_m
            ranked_drafts.append(draft)
            state.history.append(
                {
                    "agent": "preflight",
                    "placement_rank": rank,
                    "score": result.score,
                    "snap_coverage": result.snap_coverage,
                    "snap_distance_m": result.mean_snap_distance_m,
                    "shape_proxy": result.shape_fidelity,
                    "turning_proxy": result.turning_similarity,
                    "landmark_proxy": result.landmark_similarity,
                    "length_proxy": result.length_similarity,
                    "route_length_ratio": result.route_length_ratio,
                    "rotation_deg": draft.rotation_deg,
                    "scale_m": draft.scale_m,
                    "lat_offset_m": draft.lat_offset_m,
                    "lon_offset_m": draft.lon_offset_m,
                }
            )

        if not ranked_drafts:
            self._record(state, "preflight ranking was invalid; using deterministic placement")
            return state
        state.route_draft = ranked_drafts[0]
        state.placement_candidates = ranked_drafts[1:]
        self._record(
            state,
            f"preflight scanned {len(drafts)} placements; "
            f"best={ranked_drafts[0].preflight_score:.3f}, "
            f"shortlist={len(ranked_drafts)}",
        )
        return state

    @classmethod
    def _diverse_shortlist(
        cls,
        results: list[ors_client.SnapPreflightResult],
        drafts: list[RouteDraft],
        size: int,
    ) -> list[ors_client.SnapPreflightResult]:
        """Keep high-quality placements without returning near-duplicates.

        Route-choice research shows that top-k-by-cost lists often contain
        heavily overlapping alternatives. Greedy quality/diversity selection
        spends Directions calls on genuinely different city regions,
        orientations, or scales while retaining every screened placement in
        diagnostics.
        """
        valid = [
            result
            for result in results
            if 0 <= result.candidate_index < len(drafts)
        ]
        if not valid or size <= 0:
            return []
        selected = [valid.pop(0)]
        while valid and len(selected) < size:
            def utility(result: ors_client.SnapPreflightResult) -> float:
                draft = drafts[result.candidate_index]
                min_diversity = min(
                    cls._draft_diversity(
                        draft,
                        drafts[chosen.candidate_index],
                    )
                    for chosen in selected
                )
                return 0.82 * result.score + 0.18 * min_diversity

            next_result = max(valid, key=utility)
            valid.remove(next_result)
            selected.append(next_result)
        return selected

    @staticmethod
    def _draft_diversity(first: RouteDraft, second: RouteDraft) -> float:
        rotation_delta = abs(first.rotation_deg - second.rotation_deg) % 360.0
        rotation_delta = min(rotation_delta, 360.0 - rotation_delta)
        rotation = min(1.0, rotation_delta / 90.0)
        scale = min(
            1.0,
            abs(math.log(max(first.scale_m, 1.0) / max(second.scale_m, 1.0)))
            / math.log(1.35),
        )
        spatial_distance = math.hypot(
            first.lat_offset_m - second.lat_offset_m,
            first.lon_offset_m - second.lon_offset_m,
        )
        spatial = min(
            1.0,
            spatial_distance / max(600.0, 1.25 * min(first.scale_m, second.scale_m)),
        )
        return 0.50 * spatial + 0.30 * rotation + 0.20 * scale

    def _candidate_drafts(self, state: WorkflowState) -> list[RouteDraft]:
        if state.route_draft is None or state.shape is None:
            return []
        workflow = get_settings().workflow
        maximum = max(1, workflow.preflight_max_placements)
        base = state.route_draft
        placement = PlacementAgent()
        step = min(1_600.0, max(450.0, base.scale_m * 0.45))
        local_offsets = (
            (0.0, 0.0),
            (0.0, -step),
            (0.0, step),
            (-step, 0.0),
            (step, 0.0),
            (-step, -step),
            (-step, step),
            (step, -step),
            (step, step),
        )
        manual = state.map_placement
        if manual is not None:
            manual_step = min(
                manual.search_radius_m / math.sqrt(2.0),
                max(150.0, base.scale_m * 0.22),
            )
            offsets = (
                (0.0, 0.0),
                (0.0, -manual_step),
                (0.0, manual_step),
                (-manual_step, 0.0),
                (manual_step, 0.0),
                (-manual_step, -manual_step),
                (-manual_step, manual_step),
                (manual_step, -manual_step),
                (manual_step, manual_step),
            )
        else:
            offsets = self._city_grid_offsets(
                base,
                state.plan.city_bbox if state.plan else None,
            )
        if base.anchored_start is not None:
            offsets = ((0.0, 0.0),)
        elif len(offsets) < 5:
            offsets = local_offsets
        rotation_deltas = (
            (0.0,)
            if base.preferred_start_direction_deg is not None
            else (
                (0.0, -12.0, 12.0, -25.0, 25.0)
                if manual is not None
                else (0.0, 30.0, 60.0, 90.0, 120.0, 150.0)
            )
        )
        scale_factors = (1.0, 0.90, 1.10) if manual is not None else (1.0, 0.85, 1.15)
        city_bbox = (
            None
            if manual is not None
            else state.plan.city_bbox if state.plan else None
        )

        candidates: list[RouteDraft] = []
        signatures: set[tuple[float, ...]] = set()
        for scale_factor in scale_factors:
            for rotation_delta in rotation_deltas:
                for lat_delta, lon_delta in offsets:
                    # Shallow scalar copy suffices: ``project`` below replaces
                    # the waypoint list wholesale and never reads the base's.
                    draft = copy.copy(base)
                    draft.scale_m = max(25.0, base.scale_m * scale_factor)
                    draft.rotation_deg = (
                        base.rotation_deg + rotation_delta
                    ) % 360.0
                    draft.lat_offset_m = base.lat_offset_m + lat_delta
                    draft.lon_offset_m = base.lon_offset_m + lon_delta
                    draft.preflight_score = None
                    draft.preflight_coverage = None
                    draft.preflight_snap_distance_m = None
                    draft.waypoints = placement.project(state.shape, draft)
                    signature = (
                        round(draft.scale_m, 1),
                        round(draft.rotation_deg, 1),
                        round(draft.lat_offset_m, 1),
                        round(draft.lon_offset_m, 1),
                    )
                    if signature in signatures:
                        continue
                    if city_bbox and not self._inside_bbox(draft, city_bbox):
                        continue
                    signatures.add(signature)
                    candidates.append(draft)
                    if len(candidates) >= maximum:
                        return candidates
        return candidates

    @staticmethod
    def _city_grid_offsets(
        base: RouteDraft,
        bbox: tuple[float, float, float, float] | None,
    ) -> tuple[tuple[float, float], ...]:
        """Return a 3×3 city-wide translation grid plus the planned origin.

        Template-matching research shows that placement is as important as
        rotation. Sampling the municipality, instead of only nudging one city
        centre, lets the road graph reveal neighbourhoods that actually
        preserve the silhouette.
        """
        if bbox is None:
            return ()
        south, north, west, east = bbox
        if not (south < north and west < east):
            return ()
        latitudes = (
            south + (north - south) * 0.22,
            (south + north) / 2.0,
            north - (north - south) * 0.22,
        )
        longitudes = (
            west + (east - west) * 0.22,
            (west + east) / 2.0,
            east - (east - west) * 0.22,
        )

        offsets: list[tuple[float, float]] = [(0.0, 0.0)]
        for latitude in latitudes:
            lat_metres = geo.haversine(
                base.center_lat,
                base.center_lon,
                latitude,
                base.center_lon,
            )
            if latitude < base.center_lat:
                lat_metres *= -1.0
            for longitude in longitudes:
                lon_metres = geo.haversine(
                    base.center_lat,
                    base.center_lon,
                    base.center_lat,
                    longitude,
                )
                if longitude < base.center_lon:
                    lon_metres *= -1.0
                # Grid points are absolute city positions, while draft
                # offsets are relative to the geocoded centre.
                offsets.append(
                    (
                        lat_metres - base.lat_offset_m,
                        lon_metres - base.lon_offset_m,
                    )
                )
        return tuple(dict.fromkeys(offsets))

    @staticmethod
    def _inside_bbox(
        draft: RouteDraft,
        bbox: tuple[float, float, float, float],
    ) -> bool:
        south, north, west, east = bbox
        return bool(
            draft.waypoints
            and all(
                math.isfinite(lat)
                and math.isfinite(lon)
                and south <= lat <= north
                and west <= lon <= east
                for lat, lon in draft.waypoints
            )
        )
