"""ShapeAgent: turn an Intent into a normalised 2D Shape.

Three-tier fallback (each tier only runs if the previous yielded nothing):
1. Built-in template (heart, star, butterfly, ...) via keyword match.
2. Text/letter outlines when the intent carries text.
3. LLM-drawn path (the model emits an SVG-like point list).

The PlanningAgent's ``shape_strategy`` reorders the tiers (e.g. ``"text"``
tries text first, ``"llm"`` draws freely first). Without a plan the default
order is template -> text -> llm.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import OrderedDict
from threading import Lock

from shapely.geometry import LineString

from ..llm import LLMResponse, extract_json, try_complete
from ..prompts import render
from ..state import Shape, WorkflowState
from ..tools import geo, shape_library, shape_uniqueness, text_shapes
from .base import BaseAgent

_CUSTOM_SHAPE_CACHE_SIZE = 128
_CUSTOM_SHAPE_CACHE_VERSION = "v3"
_CUSTOM_SHAPE_CACHE: OrderedDict[tuple[str, str], Shape] = OrderedDict()
_CUSTOM_SHAPE_CACHE_LOCK = Lock()

_CUSTOM_SHAPE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "maxLength": 80},
        "paths": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "array",
                "minItems": 6,
                "maxItems": 240,
                "items": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {"type": "number", "minimum": -10, "maximum": 10},
                },
            },
        },
        "closed": {"type": "boolean"},
    },
    "required": ["name", "paths", "closed"],
    "additionalProperties": False,
}


class ShapeAgent(BaseAgent):
    name = "shape"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.intent is None:
            raise RuntimeError("shape generation requires intent")
        for tier in self._ordered_tiers(state):
            shape = tier(state)
            if shape is not None:
                break
        else:  # ultimate safety net — always produce a shape
            name, paths, closed = shape_library.star()
            shape = Shape(name=name, paths=[list(p) for p in paths], closed=closed, source="fallback")
        # Smooth jagged LLM paths before the single normalisation pass.
        # Templates and text are already sampled appropriately; extra passes
        # would inflate CPU work and route payloads without adding detail.
        shape.paths = self._smooth(shape)
        shape.paths = geo.normalize_shape(shape.paths)
        state.shape = shape
        if shape.source == "fallback":
            requested = state.intent.shape if state.intent else None
            state.errors.append(
                f"shape: we couldn't build a reliable custom outline for "
                f"{requested or 'this idea'!r}; using the clearly labelled "
                f"{shape.name!r} fallback"
            )
        self._record(state, f"shape={shape.name} source={shape.source} paths={len(shape.paths)}")
        return state

    def _smooth(self, shape: Shape) -> list[list[tuple[float, float]]]:
        if shape.source == "llm":
            smoothed: list[geo.Path] = []
            for path in shape.paths:
                candidate = geo.catmull_rom_smooth(
                    path,
                    closed=shape.closed,
                    subdivisions=3,
                    corner_threshold_deg=70.0,
                )
                # Even the stable centripetal curve can cross a remote segment
                # in a strongly concave whole outline. Keep the authored
                # control polygon whenever that executable topology check fails.
                smoothed.append(candidate if _is_simple_path(candidate) else list(path))
            return smoothed
        return shape.paths

    def _ordered_tiers(self, state: WorkflowState) -> list:
        strategy = state.plan.shape_strategy if state.plan else "template"
        tiers = {
            "text": [self._try_text, self._try_template, self._try_llm],
            "llm": [self._try_llm, self._try_template, self._try_text],
            "template": [self._try_template, self._try_text, self._try_llm],
        }
        return tiers.get(strategy, tiers["template"])

    # -- tier 1: template --------------------------------------------------- #
    def _try_template(self, state: WorkflowState) -> Shape | None:
        intent = state.intent
        if intent is None:
            return None
        idea = intent.shape
        if not idea:
            return None
        hit = shape_library.get_shape(idea)
        if hit is None:
            hit = shape_library.find_by_keyword(idea)
            if hit and not shape_library.template_match_covers_description(
                idea,
                hit[0],
            ):
                return None
        if not hit:
            return None
        name, paths, closed = hit
        return Shape(name=name, paths=[list(p) for p in paths], closed=closed, source="template")

    # -- tier 2: text ------------------------------------------------------- #
    def _try_text(self, state: WorkflowState) -> Shape | None:
        intent = state.intent
        if intent is None:
            return None
        text = intent.text
        if not text:
            return None
        paths, closed = text_shapes.text_to_shape(text)
        if not any(len(path) >= 2 for path in paths):
            return None
        return Shape(name=f"text:{text}", paths=paths, closed=closed, source="text")

    # -- tier 3: LLM-drawn -------------------------------------------------- #
    def _try_llm(self, state: WorkflowState) -> Shape:
        intent = state.intent
        if intent is None:
            return self._llm_fallback_shape("custom idea")
        idea = intent.shape or "an interesting shape"
        style = intent.style or "none"
        cache_key = _custom_shape_cache_key(idea, style)
        cached = _get_cached_custom_shape(cache_key, name=idea)
        if cached is not None:
            return cached

        system = self.system_prompt
        user = render(
            "shape",
            shape=json.dumps(idea, ensure_ascii=False),
            style=json.dumps(style, ensure_ascii=False),
        )
        resp = try_complete(
            lambda: self._llm_fallback(idea),
            messages=[{"role": "user", "content": user}],
            system=system,
            json_mode=True,
            json_schema=_CUSTOM_SHAPE_JSON_SCHEMA,
            temperature=0.3,
        )
        try:
            shape = _shape_from_response(resp, idea)
        except (KeyError, TypeError, ValueError) as exc:
            shape = self._repair_or_fallback(
                idea=idea,
                user=user,
                system=system,
                reason=str(exc),
                provider_was_available=resp.provider != "fallback",
            )

        if shape.source == "llm":
            _cache_custom_shape(cache_key, shape)
        return shape

    def _repair_or_fallback(
        self,
        *,
        idea: str,
        user: str,
        system: str,
        reason: str,
        provider_was_available: bool,
    ) -> Shape:
        if not provider_was_available:
            return self._llm_fallback_shape(idea)

        safe_reason = " ".join(reason.split())[:240]
        self.log.warning(
            "custom shape geometry rejected (%s); requesting one bounded repair",
            safe_reason,
        )
        repair_prompt = (
            f"{user}\n\n"
            "The previous geometry failed an executable validation check: "
            f"{safe_reason}. Regenerate it from scratch. Keep one simple, "
            "continuous silhouette, close it exactly, and return only the JSON schema."
        )
        repaired = try_complete(
            lambda: self._llm_fallback(idea),
            messages=[{"role": "user", "content": repair_prompt}],
            system=system,
            json_mode=True,
            json_schema=_CUSTOM_SHAPE_JSON_SCHEMA,
            temperature=0.2,
        )
        try:
            return _shape_from_response(repaired, idea)
        except (KeyError, TypeError, ValueError):
            return self._llm_fallback_shape(idea)

    def _llm_fallback(self, idea: str) -> LLMResponse:
        fallback = _label_fallback_shape(idea)
        payload = {
            "name": fallback.name,
            "paths": [[[x, y] for x, y in path] for path in fallback.paths],
            "closed": fallback.closed,
        }
        return LLMResponse(text=json.dumps(payload), provider="fallback", model="rules")

    def _llm_fallback_shape(self, idea: str) -> Shape:
        return _label_fallback_shape(idea)


def _shape_from_response(resp: LLMResponse, idea: str) -> Shape:
    data = extract_json(resp.text)
    if not isinstance(data, dict):
        raise ValueError("response must be a JSON object")
    closed = _parse_bool(data.get("closed", False))
    paths = _validated_paths(data.get("paths"), closed=closed)
    source = "fallback" if resp.provider == "fallback" else "llm"
    if source == "llm":
        _validate_route_friendly_geometry(paths)
        _validate_distinct_custom_geometry(paths)
        name = " ".join(idea.split())[:80]
    else:
        raw_name = data.get("name")
        name = (
            " ".join(raw_name.split())[:80]
            if isinstance(raw_name, str) and raw_name.strip()
            else _label_fallback_shape(idea).name
        )
    return Shape(name=name, paths=paths, closed=closed, source=source)


def _validated_paths(value: object, *, closed: bool = False) -> list[geo.Path]:
    """Validate and bound untrusted model-generated drawing geometry."""
    if not isinstance(value, list):
        raise ValueError("paths must be a list")

    paths: list[geo.Path] = []
    total_points = 0
    for raw_stroke in value[:8]:
        if not isinstance(raw_stroke, list):
            continue
        stroke: geo.Path = []
        for raw_point in raw_stroke:
            if (
                not isinstance(raw_point, (list, tuple))
                or len(raw_point) != 2
                or isinstance(raw_point[0], bool)
                or isinstance(raw_point[1], bool)
            ):
                continue
            try:
                point = (float(raw_point[0]), float(raw_point[1]))
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(coordinate) for coordinate in point):
                continue
            if max(abs(point[0]), abs(point[1])) > 1_000_000:
                continue
            if not stroke or point != stroke[-1]:
                stroke.append(point)
        if len(stroke) < 2:
            continue
        if len(stroke) > 240:
            indices = [
                round(index * (len(stroke) - 1) / 239)
                for index in range(240)
            ]
            stroke = [stroke[index] for index in indices]
        if closed and stroke[0] != stroke[-1]:
            stroke.append(stroke[0])
        total_points += len(stroke)
        if total_points > 800:
            break
        paths.append(stroke)

    if not paths:
        raise ValueError("paths contain no drawable strokes")
    return paths


def _validate_route_friendly_geometry(paths: list[geo.Path]) -> None:
    """Reject geometry that cannot be a credible street-route scaffold."""

    total_points = sum(len(path) for path in paths)
    if total_points < 6:
        raise ValueError("the outline needs at least six control points")
    if max(abs(coordinate) for path in paths for point in path for coordinate in point) > 10:
        raise ValueError("shape coordinates must stay between -10 and 10")

    normalised = geo.normalize_shape(paths)
    points = [point for path in normalised for point in path]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    shorter = min(width, height)
    if max(width, height) < 1e-6 or shorter < 1e-3:
        raise ValueError("the outline collapses to a point or straight line")
    if max(width, height) / shorter > 4.0:
        raise ValueError("the outline aspect ratio is too extreme for street routing")

    for path in normalised:
        if len(path) >= 4 and not _is_simple_path(path):
            raise ValueError("the outline crosses itself")

    if len(normalised) > 1:
        authored_length = geo.unit_perimeter(normalised)
        stitched_length = geo.unit_path_length(geo.stitch_paths(normalised))
        transfer_length = max(0.0, stitched_length - authored_length)
        if authored_length <= 1e-9 or transfer_length / authored_length > 0.45:
            raise ValueError(
                "separate strokes require too much artificial route transfer; "
                "use one silhouette or move essential strokes closer"
            )


def _validate_distinct_custom_geometry(paths: list[geo.Path]) -> None:
    """Keep a free-text result from silently collapsing to a stock template."""

    match = shape_uniqueness.nearest_catalog_shape(paths)
    if match.distance <= shape_uniqueness.DUPLICATE_DISTANCE_THRESHOLD:
        raise ValueError(
            f"the custom outline duplicates the built-in {match.name!r} route; "
            "represent the request's own distinguishing silhouette features"
        )


def _is_simple_path(path: geo.Path) -> bool:
    if len(path) < 4:
        return True
    try:
        return bool(LineString(path).is_simple)
    except (TypeError, ValueError):
        return False


def _label_fallback_shape(idea: str) -> Shape:
    """Return an honest, idea-linked offline fallback instead of a fake icon."""

    ascii_idea = unicodedata.normalize("NFKD", idea).encode("ascii", "ignore").decode()
    match = re.search(r"[A-Za-z0-9]", ascii_idea)
    if match:
        glyph = match.group(0).upper()
        paths, closed = text_shapes.text_to_shape(glyph)
        if any(len(path) >= 2 for path in paths):
            return Shape(
                name=f"{glyph} label",
                paths=[list(path) for path in paths],
                closed=closed,
                source="fallback",
            )

    name, paths, closed = shape_library.star()
    return Shape(name=name, paths=[list(path) for path in paths], closed=closed, source="fallback")


def _custom_shape_cache_key(idea: str, style: str) -> tuple[str, str]:
    normalized = "\0".join(
        (
            " ".join(idea.casefold().split()),
            " ".join(style.casefold().split()),
        )
    )
    return _CUSTOM_SHAPE_CACHE_VERSION, hashlib.sha256(normalized.encode()).hexdigest()


def _get_cached_custom_shape(key: tuple[str, str], *, name: str) -> Shape | None:
    with _CUSTOM_SHAPE_CACHE_LOCK:
        cached = _CUSTOM_SHAPE_CACHE.get(key)
        if cached is None:
            return None
        _CUSTOM_SHAPE_CACHE.move_to_end(key)
        shape = _clone_shape(cached)
        shape.name = " ".join(name.split())[:80]
        return shape


def _cache_custom_shape(key: tuple[str, str], shape: Shape) -> None:
    with _CUSTOM_SHAPE_CACHE_LOCK:
        cached = _clone_shape(shape)
        # Do not retain arbitrary user wording in the cache value; the key is
        # hashed and the request-local name is restored on cache lookup.
        cached.name = ""
        _CUSTOM_SHAPE_CACHE[key] = cached
        _CUSTOM_SHAPE_CACHE.move_to_end(key)
        while len(_CUSTOM_SHAPE_CACHE) > _CUSTOM_SHAPE_CACHE_SIZE:
            _CUSTOM_SHAPE_CACHE.popitem(last=False)


def _clear_custom_shape_cache() -> None:
    with _CUSTOM_SHAPE_CACHE_LOCK:
        _CUSTOM_SHAPE_CACHE.clear()


def _clone_shape(shape: Shape) -> Shape:
    return Shape(
        name=shape.name,
        paths=[list(path) for path in shape.paths],
        closed=shape.closed,
        source=shape.source,
    )


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if isinstance(value, int | float):
        return value == 1
    return False
