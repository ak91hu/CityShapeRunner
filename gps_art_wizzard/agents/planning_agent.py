"""PlanningAgent: commit a strategy before any drawing happens.

Runs once, after Intent and before Shape. Geocodes the city early so it can
reason about the actual map: street-grid orientation, rivers, parks, and the
best area to place the shape. Decides the shape strategy, difficulty, rotation,
scale, and placement offsets. The ShapeAgent and PlacementAgent read the plan
instead of guessing independently.
"""

from __future__ import annotations

import json
import math
import re

from ..llm import LLMResponse, extract_json, try_complete
from ..prompts import render
from ..state import Plan, WorkflowState
from ..tools import geo, geocoder, shape_library, shape_recommender
from .base import BaseAgent


class PlanningAgent(BaseAgent):
    name = "planning"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.intent is None:
            raise RuntimeError("planning requires intent")
        # Geocode early so the plan can be map-aware.
        city = state.intent.city or "Budapest"
        geo_result = geocoder.geocode(city)
        if geo_result.substituted:
            state.errors.append(
                f"geocoding: {city!r} could not be resolved; using {geo_result.name!r}"
            )
            city = geo_result.name
            state.intent.city = geo_result.name
        extent_heading = geo.bbox_long_axis_heading(geo_result.bbox)
        map_context = geocoder.city_context(city, geo_result)

        # When the user asks for a suggestion, list the available shapes so the
        # LLM can pick the one that best fits the city's geography.
        available_shapes = sorted(shape_library.SHAPES.keys()) if state.intent.suggest else []

        intent_blob = json.dumps(state.intent.__dict__, default=str, ensure_ascii=False)
        user = render(
            "plan",
            intent=intent_blob,
            city=city,
            center_lat=f"{geo_result.lat:.4f}",
            center_lon=f"{geo_result.lon:.4f}",
            city_extent_heading=f"{extent_heading:.0f}",
            map_context=map_context,
            available_shapes=", ".join(available_shapes),
            suggest="true" if state.intent.suggest else "false",
        )
        fallback = self._fallback(state, extent_heading, map_context)
        known_template = bool(
            state.intent.shape
            and (
                shape_library.get_shape(state.intent.shape)
                or shape_library.find_by_keyword(state.intent.shape)
            )
        )
        if known_template or state.intent.text or state.intent.suggest:
            # Geometry for known templates is numeric and should be stable.
            # Reserve the LLM planner for unsupported/free-form shapes.
            resp = fallback
        else:
            resp = try_complete(
                lambda: fallback,
                messages=[{"role": "user", "content": user}],
                system=self.system_prompt,
                json_mode=True,
                temperature=0.1,
            )
        state.plan = self._parse(resp.text, state)
        state.plan.center_lat = geo_result.lat
        state.plan.center_lon = geo_result.lon
        state.plan.city_bbox = geo_result.bbox
        state.plan.fallback_candidates = self._fallback_candidates(
            map_context,
            state.intent.sport,
            city=city,
            requested=state.intent.shape,
        )

        # Suggestions must remain conservative: an LLM cannot inspect the ORS
        # graph and tended to choose complex butterflies for sparse/hilly
        # cities. Geographic context selects a bounded, street-friendly shape.
        if state.intent.suggest:
            recommendations = shape_recommender.recommend_shapes(
                city,
                map_context,
                state.intent.sport,
                state.intent.distance_km,
            )
            candidates = [item.name for item in recommendations]
            state.plan.suggested_shape = candidates[0]
            state.plan.suggestion_candidates = candidates
            state.plan.suggestion_reasons = {
                item.name: item.reason for item in recommendations
            }
            state.plan.notes = recommendations[0].reason

        # If a shape was suggested, override the intent so ShapeAgent uses it.
        if state.plan.suggested_shape:
            state.intent.shape = state.plan.suggested_shape
            state.intent.suggest = False  # consumed

        self._record(
            state,
            f"plan: strategy={state.plan.shape_strategy} difficulty={state.plan.difficulty} "
            f"rot={state.plan.rotation_hint_deg} offsets=({state.plan.lat_offset_m},{state.plan.lon_offset_m})"
            + (f" suggested={state.plan.suggested_shape}" if state.plan.suggested_shape else ""),
        )
        return state

    # -- parsing ----------------------------------------------------------- #
    def _parse(self, text: str, state: WorkflowState) -> Plan:
        try:
            data = extract_json(text)
        except Exception:  # noqa: BLE001
            data = {}
        data = data if isinstance(data, dict) else {}
        strategy = str(data.get("shape_strategy") or "").lower()
        if strategy not in ("template", "text", "llm"):
            strategy = self._fallback_strategy(state)
        difficulty = str(data.get("difficulty") or "medium").lower()
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        # Parse the AI-suggested shape (if any) and validate it exists.
        suggested = str(data.get("suggested_shape") or "").lower().strip()
        if suggested and not shape_library.get_shape(suggested):
            suggested = ""

        rotation = _num(data.get("rotation_hint_deg"))
        scale_hint = _num(data.get("scale_hint"))
        lat_offset = _num(data.get("lat_offset_m"))
        lon_offset = _num(data.get("lon_offset_m"))
        return Plan(
            shape_strategy=strategy,
            difficulty=difficulty,
            rotation_hint_deg=rotation % 360.0 if rotation is not None else None,
            scale_hint=min(4.0, max(0.25, scale_hint)) if scale_hint is not None else None,
            placement_hints=_optional_text(data.get("placement_hints"), 500),
            notes=_optional_text(data.get("notes"), 500),
            lat_offset_m=min(20_000.0, max(-20_000.0, lat_offset or 0.0)),
            lon_offset_m=min(20_000.0, max(-20_000.0, lon_offset or 0.0)),
            suggested_shape=suggested or None,
        )

    # -- deterministic fallback -------------------------------------------- #
    def _fallback_strategy(self, state: WorkflowState) -> str:
        intent = state.intent
        if intent is None:
            raise RuntimeError("planning fallback requires intent")
        if intent.text:
            return "text"
        idea = intent.shape
        if idea and (shape_library.get_shape(idea) or shape_library.find_by_keyword(idea)):
            return "template"
        return "llm"

    def _fallback(self, state: WorkflowState, extent_heading: float, map_context: str) -> LLMResponse:
        intent = state.intent
        if intent is None:
            raise RuntimeError("planning fallback requires intent")
        strategy = self._fallback_strategy(state)
        difficulty = "medium"
        if strategy == "llm":
            difficulty = "hard"
        elif intent.text:
            difficulty = "medium"
        else:
            difficulty = "easy"

        # Heuristic shape suggestion: pick based on city characteristics.
        suggested = None
        if intent.suggest:
            suggested = self._heuristic_suggest(
                map_context,
                intent.sport,
                city=intent.city or "",
                distance_km=intent.distance_km,
            )
            strategy = "template"

        lat_offset_m, lon_offset_m = self._placement_offset(map_context)
        payload = {
            "shape_strategy": strategy,
            "difficulty": difficulty,
            "rotation_hint_deg": self._rotation_from_context(
                map_context, extent_heading
            ),
            "scale_hint": None,
            "placement_hints": map_context[:200],
            "notes": None,
            "lat_offset_m": lat_offset_m,
            "lon_offset_m": lon_offset_m,
            "suggested_shape": suggested,
        }
        return LLMResponse(text=json.dumps(payload), provider="fallback", model="rules")

    @staticmethod
    def _placement_offset(map_context: str) -> tuple[float, float]:
        """Derive a conservative offset from the curated city description."""
        low = map_context.lower()
        # The descriptions deliberately use "place shapes <direction>" for a
        # safe side of a river, lake, park, or hill. Use only the first nearby
        # directional recommendation; refinement explores local alternatives.
        placement = low[low.find("place shapes") :] if "place shapes" in low else ""
        placement = placement[:180].split(".", maxsplit=1)[0]
        step = 1_500.0
        lat = step if re.search(r"\bnorth\b", placement) else (
            -step if re.search(r"\bsouth\b", placement) else 0.0
        )
        lon = step if re.search(r"\beast\b", placement) else (
            -step if re.search(r"\bwest\b", placement) else 0.0
        )
        return lat, lon

    @staticmethod
    def _rotation_from_context(map_context: str, fallback: float) -> float:
        """Prefer the curated street-grid bearing over a city bbox heading."""
        match = re.search(
            r"\brotation\s*(?:of|:|=|~)?\s*(-?\d+(?:\.\d+)?)",
            map_context,
            flags=re.IGNORECASE,
        )
        return float(match.group(1)) % 360.0 if match else round(fallback) % 360.0

    def _heuristic_suggest(
        self,
        map_context: str,
        sport: str,
        *,
        city: str = "",
        distance_km: float | None = None,
    ) -> str:
        """Pick the highest-scoring shape after analysing the full registry."""
        recommendations = shape_recommender.recommend_shapes(
            city,
            map_context,
            sport,
            distance_km,
            limit=1,
        )
        return recommendations[0].name

    def _suggestion_candidates(
        self,
        map_context: str,
        sport: str,
        *,
        city: str,
        distance_km: float | None = None,
    ) -> list[str]:
        """Return three ranked, diverse shapes for measured graph evaluation."""
        return [
            item.name
            for item in shape_recommender.recommend_shapes(
                city,
                map_context,
                sport,
                distance_km,
            )
        ]

    def _fallback_candidates(
        self,
        map_context: str,
        sport: str,
        *,
        city: str,
        requested: str | None,
    ) -> list[str]:
        """Return simple alternatives worth measuring when an idea fails.

        These are not accepted on a city-name heuristic alone.  The
        orchestrator routes and validates every candidate before it may replace
        the requested drawing.
        """
        low = map_context.casefold()
        topology_order: tuple[str, ...]
        if any(
            word in low
            for word in ("hilly", "irregular", "winding", "hills", "sparse", "limited")
        ):
            topology_order = ("triangle", "diamond", "arrow", "moon")
        elif any(word in low for word in ("river", "lake", "water", "confluence")):
            topology_order = ("arrow", "diamond", "triangle", "heart")
        else:
            topology_order = ("heart", "triangle", "diamond", "arrow", "square")

        city_primary = self._heuristic_suggest(map_context, sport, city=city)
        safe_primary = (
            city_primary
            if city_primary in {"heart", "triangle", "diamond", "arrow", "square", "cross", "moon"}
            else None
        )
        requested_key = (requested or "").casefold().strip()
        candidates: list[str] = []
        for name in (safe_primary, *topology_order):
            if (
                name
                and name != requested_key
                and name not in candidates
                and shape_library.get_shape(name)
            ):
                candidates.append(name)
            if len(candidates) == 3:
                break
        return candidates


def _num(v) -> float | None:
    try:
        number = float(v) if v is not None and not isinstance(v, bool) else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and math.isfinite(number) else None


def _optional_text(value: object, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:max_length] or None
