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

import json
import math

from ..llm import LLMResponse, extract_json, try_complete
from ..prompts import render
from ..state import Shape, WorkflowState
from ..tools import geo, shape_library, text_shapes
from .base import BaseAgent


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
            state.errors.append(
                f"shape: requested drawing was unavailable; using the {shape.name!r} fallback"
            )
        self._record(state, f"shape={shape.name} source={shape.source} paths={len(shape.paths)}")
        return state

    def _smooth(self, shape: Shape) -> list[list[tuple[float, float]]]:
        if shape.source == "llm":
            return [geo.catmull_rom_smooth(p, closed=shape.closed, subdivisions=6) for p in shape.paths]
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
        hit = shape_library.get_shape(idea) or shape_library.find_by_keyword(idea)
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
            return self._llm_fallback_shape()
        idea = intent.shape or "an interesting shape"
        system = self.system_prompt
        user = render("shape", shape=idea, style=intent.style or "none")
        resp = try_complete(
            self._llm_fallback,
            messages=[{"role": "user", "content": user}],
            system=system,
            json_mode=True,
            temperature=0.3,
        )
        try:
            data = extract_json(resp.text)
            paths = _validated_paths(data.get("paths"))
            closed = _parse_bool(data.get("closed", False))
            raw_name = data.get("name")
            name = " ".join(raw_name.split())[:80] if isinstance(raw_name, str) else idea
            source = "fallback" if resp.provider == "fallback" else "llm"
            return Shape(name=name, paths=paths, closed=closed, source=source)
        except (KeyError, TypeError, ValueError):
            return self._llm_fallback_shape()

    def _llm_fallback(self) -> LLMResponse:
        # Last resort LLM response: a star so the pipeline still produces *something*.
        name, paths, closed = shape_library.star()
        payload = {
            "name": name,
            "paths": [[[x, y] for x, y in p] for p in paths],
            "closed": closed,
        }
        return LLMResponse(text=json.dumps(payload), provider="fallback", model="rules")

    def _llm_fallback_shape(self) -> Shape:
        name, paths, closed = shape_library.star()
        return Shape(name=name, paths=[list(p) for p in paths], closed=closed, source="fallback")


def _validated_paths(value: object) -> list[geo.Path]:
    """Validate and bound untrusted model-generated drawing geometry."""
    if not isinstance(value, list):
        raise ValueError("paths must be a list")

    paths: list[geo.Path] = []
    total_points = 0
    for raw_stroke in value[:16]:
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
        if len(stroke) > 1_000:
            indices = [
                round(index * (len(stroke) - 1) / 999)
                for index in range(1_000)
            ]
            stroke = [stroke[index] for index in indices]
        total_points += len(stroke)
        if total_points > 5_000:
            break
        paths.append(stroke)

    if not paths:
        raise ValueError("paths contain no drawable strokes")
    return paths


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if isinstance(value, int | float):
        return value == 1
    return False
