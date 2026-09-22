"""PreflightAgent: cheaply rank shape placements before full routing.

The expensive Directions endpoint is a poor search primitive. This agent
generates a broad set of scale/rotation/translation candidates, batch-snaps
their sparse guide points to the road graph in one request, and keeps only the
best placements for measured Directions routing.
"""

from __future__ import annotations

import copy
import math
import time
from dataclasses import replace

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
        adaptive = getattr(workflow, "preflight_adaptive", False)
        if adaptive and len(drafts) > 12:
            # Sample the whole transform space, rather than truncating the
            # scale-major enumeration and losing its later orientations.
            count = max(12, int(workflow.preflight_max_placements * 0.55))
            drafts = self._spread_drafts(drafts, min(count, len(drafts)))
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

        results = self._valid_results(results, len(drafts))
        # Graph evidence complements independent point snaps. A local snapshot
        # can improve ranking without changing the export authority.
        from ..tools.street_graph import graph_for_state
        graph = graph_for_state(state) if hasattr(get_settings(), "routing") else None
        results = self._network_rank(results, drafts, graph)
        if adaptive:
            for round_index in (1, 2):
                remaining = max(0, workflow.preflight_max_placements - len(drafts))
                budget = remaining if round_index == 2 else (remaining + 1) // 2
                seeds = self._diverse_shortlist(results, drafts, 4)
                fine = self._refined_drafts(state, drafts, seeds, budget, round_index)
                if not fine:
                    break
                measured = ors_client.preflight_route_candidates(
                    [draft.waypoints for draft in fine],
                    sport=state.intent.sport,
                    closed=state.shape.closed,
                    max_guide_points=workflow.preflight_guide_points,
                )
                state.preflight_count += len(fine)
                if measured is None:
                    # Preserve the measured coarse results if the next batch
                    # is unavailable; no repeated provider retry here.
                    self._record(state, "adaptive preflight unavailable; retaining measured placements")
                    break
                offset = len(drafts)
                drafts.extend(fine)
                measured = self._network_rank(self._valid_results(measured, len(fine)), fine, graph)
                results.extend(
                    replace(result, candidate_index=offset + result.candidate_index)
                    for result in self._valid_results(measured, len(fine))
                )
                results = self._valid_results(results, len(drafts))
                state.history.append({
                    "agent": "preflight", "adaptive_round": round_index,
                    "placements": len(fine), "best_score": results[0].score if results else None,
                })

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
                    "network_connectivity": result.network_connectivity,
                    "network_detour_ratio": result.network_detour_ratio,
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

    @staticmethod
    def _network_rank(results, drafts, graph):
        if graph is None:
            return results
        from ..tools.street_graph import connectivity_proxy
        ranked = list(results)
        deadline = time.monotonic() + 0.4
        for index, result in enumerate(ranked[:21]):
            if time.monotonic() > deadline:
                break
            guides = ors_client._subsample(drafts[result.candidate_index].waypoints, closed=drafts[result.candidate_index].closed, max_points=6)
            connected, detour = connectivity_proxy(graph, guides)
            penalty = 0.08 if connected == 0 else 1 / (1 + max(0, (detour or 1) - 1) * 0.25)
            ranked[index] = replace(result, score=result.score * penalty,
                                    network_connectivity=connected, network_detour_ratio=detour)
        return sorted(ranked, key=lambda result: (-result.score, result.candidate_index))

    @staticmethod
    def _valid_results(results, count):
        return sorted(
            (r for r in results if 0 <= r.candidate_index < count and math.isfinite(r.score)),
            key=lambda r: (-r.score, r.candidate_index),
        )

    @classmethod
    def _spread_drafts(cls, drafts: list[RouteDraft], count: int) -> list[RouteDraft]:
        if count >= len(drafts):
            return drafts
        chosen = [drafts[0]]
        available = list(drafts[1:])
        distances = [cls._draft_diversity(d, chosen[0]) for d in available]
        while available and len(chosen) < count:
            index = max(range(len(available)), key=lambda i: distances[i])
            selected = available.pop(index)
            distances.pop(index)
            chosen.append(selected)
            distances = [min(old, cls._draft_diversity(d, selected))
                         for d, old in zip(available, distances, strict=True)]
        return chosen

    @staticmethod
    def _signature(draft: RouteDraft) -> tuple[float, ...]:
        return (round(draft.scale_m, 1), round(draft.rotation_deg % 360, 1),
                round(draft.lat_offset_m, 1), round(draft.lon_offset_m, 1))

    def _refined_drafts(self, state, drafts, seeds, budget, round_index):
        if not seeds or budget <= 0 or state.shape is None:
            return []
        seen = {self._signature(draft) for draft in drafts}
        proposed = []
        projector = PlacementAgent()
        # Round-robin over seeds prevents the best neighbourhood consuming
        # every fine sample before alternative neighbourhoods are examined.
        variants = ((0, 0, 1, 0), (0, 0, -1, 0), (0, 0, 0, 1), (0, 0, 0, -1),
                    (1, 0, 0, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, -1, 0, 0),
                    (0, 0, 1, 1), (0, 0, -1, -1), (1, 1, 0, 0), (-1, -1, 0, 0),
                    (1, 0, 1, 0), (-1, 0, -1, 0), (0, 1, 0, 1), (0, -1, 0, -1))
        for rotation, scale, north, east in variants:
            for seed in seeds:
                base = drafts[seed.candidate_index]
                step = min(450.0, max(60.0, base.scale_m * 0.18)) / round_index
                draft = copy.copy(base)
                draft.scale_m = max(25.0, base.scale_m * (1 + scale * 0.075 / round_index))
                if base.preferred_start_direction_deg is None:
                    draft.rotation_deg = (base.rotation_deg + rotation * 10 / round_index) % 360
                if base.anchored_start is None:
                    draft.lat_offset_m += north * step
                    draft.lon_offset_m += east * step
                manual = state.map_placement
                if manual and math.hypot(draft.lat_offset_m, draft.lon_offset_m) > manual.search_radius_m:
                    continue
                draft.waypoints = projector.project(state.shape, draft)
                bbox = state.plan.city_bbox if state.plan and manual is None else None
                if bbox and not self._inside_bbox(draft, bbox):
                    continue
                signature = self._signature(draft)
                if signature in seen:
                    continue
                seen.add(signature)
                proposed.append(draft)
                if len(proposed) >= budget:
                    return proposed
        return proposed

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
        offsets: tuple[tuple[float, float], ...]
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
