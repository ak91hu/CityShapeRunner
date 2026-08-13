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
from copy import deepcopy
from dataclasses import asdict, dataclass
from threading import Lock

from shapely.geometry import LineString

from ..config import get_settings
from ..llm import ImageInput, LLMResponse, extract_json, try_complete
from ..prompts import render
from ..state import (
    Shape,
    ShapeCueVerification,
    ShapeFeature,
    ShapePart,
    ShapeSpec,
    ShapeVerification,
    WorkflowState,
)
from ..tools import geo, shape_library, shape_program, shape_uniqueness, text_shapes
from .base import BaseAgent

_CUSTOM_SHAPE_CACHE_SIZE = 128
_CUSTOM_SHAPE_CACHE_VERSION = "v6"
_CUSTOM_SHAPE_CACHE: OrderedDict[tuple[str, str], Shape] = OrderedDict()
_CUSTOM_SHAPE_CACHE_LOCK = Lock()

_POINT_SCHEMA = {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "items": {"type": "number", "minimum": -10, "maximum": 10},
}

_SHAPE_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": ["move", "line", "curve", "close"]},
        "points": {"type": "array", "minItems": 0, "maxItems": 3, "items": _POINT_SCHEMA},
        "feature_id": {"type": ["string", "null"], "maxLength": 48},
    },
    "required": ["op", "points", "feature_id"],
    "additionalProperties": False,
}

_SHAPE_PROGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "strokes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 96,
                        "items": _SHAPE_COMMAND_SCHEMA,
                    }
                },
                "required": ["commands"],
                "additionalProperties": False,
            },
        },
        "closed": {"type": "boolean"},
    },
    "required": ["strokes", "closed"],
    "additionalProperties": False,
}

_CUSTOM_SHAPE_VARIANT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy": {"type": "string", "minLength": 3, "maxLength": 120},
        "program": _SHAPE_PROGRAM_SCHEMA,
    },
    "required": ["strategy", "program"],
    "additionalProperties": False,
}

_CUSTOM_SHAPE_JSON_SCHEMA = {
    "type": "object",
    "description": "Adaptive route-native candidate programs for the requested GPS art.",
    "properties": {
        "name": {"type": "string", "maxLength": 80},
        "variants": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": _CUSTOM_SHAPE_VARIANT_JSON_SCHEMA,
        },
        "preferred_variant": {"type": "integer", "minimum": 0, "maximum": 3},
    },
    "required": ["name", "variants", "preferred_variant"],
    "additionalProperties": False,
}

_SHAPE_SPEC_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string", "minLength": 1, "maxLength": 80},
        "modifiers": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 80}},
        "pose": {"type": "string", "maxLength": 120},
        "viewpoint": {"type": "string", "enum": ["front", "side", "three-quarter", "symbolic", "unspecified"]},
        "parts": {
            "type": "array",
            "minItems": 2,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1, "maxLength": 48},
                    "label": {"type": "string", "minLength": 1, "maxLength": 80},
                    "parent": {"type": ["string", "null"], "maxLength": 48},
                    "required": {"type": "boolean"},
                    "relative_size": {"type": "string", "enum": ["small", "medium", "large", "dominant"]},
                    "position": {"type": "string", "maxLength": 120},
                },
                "required": ["id", "label", "parent", "required", "relative_size", "position"],
                "additionalProperties": False,
            },
        },
        "recognition_features": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1, "maxLength": 48},
                    "label": {"type": "string", "minLength": 4, "maxLength": 120},
                    "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                    "geometry_hint": {"type": "string", "maxLength": 160},
                    "relation": {"type": "string", "maxLength": 160},
                },
                "required": ["id", "label", "importance", "geometry_hint", "relation"],
                "additionalProperties": False,
            },
        },
        "symmetry": {"type": "string", "enum": ["none", "approximate", "bilateral", "radial"]},
        "preferred_strokes": {"type": "integer", "minimum": 1, "maximum": 4},
        "closed_silhouette": {"type": "boolean"},
        "aspect_ratio": {"type": "number", "minimum": 0.5, "maximum": 2.0},
        "ambiguity": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "subject", "modifiers", "pose", "viewpoint", "parts",
        "recognition_features", "symmetry", "preferred_strokes",
        "closed_silhouette", "aspect_ratio", "ambiguity",
    ],
    "additionalProperties": False,
}

_SHAPE_REPAIR_JSON_SCHEMA = {
    "type": "object",
    "properties": {"candidate": _CUSTOM_SHAPE_VARIANT_JSON_SCHEMA},
    "required": ["candidate"],
    "additionalProperties": False,
}

_SHAPE_VERIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "candidate_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "subject_match": {"type": "number", "minimum": 0, "maximum": 1},
                    "silhouette_quality": {"type": "number", "minimum": 0, "maximum": 1},
                    "route_readability": {"type": "number", "minimum": 0, "maximum": 1},
                    "cue_results": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "properties": {
                                "feature_id": {"type": "string", "maxLength": 48},
                                "present": {"type": "boolean"},
                                "score": {"type": "number", "minimum": 0, "maximum": 1},
                                "reason": {"type": "string", "maxLength": 180},
                            },
                            "required": ["feature_id", "present", "score", "reason"],
                            "additionalProperties": False,
                        },
                    },
                    "missing_features": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 48}},
                    "wrong_relations": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 160}},
                    "repair_instructions": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 180}},
                },
                "required": [
                    "candidate_index", "score", "subject_match", "silhouette_quality",
                    "route_readability", "cue_results", "missing_features",
                    "wrong_relations", "repair_instructions",
                ],
                "additionalProperties": False,
            },
        },
        "recommended_candidate": {"type": "integer", "minimum": 0, "maximum": 3},
    },
    "required": ["reviews", "recommended_candidate"],
    "additionalProperties": False,
}


@dataclass
class _GeneratedCandidate:
    index: int
    strategy: str
    raw: dict
    shape: Shape
    local_score: float
    feature_warnings: list[str]
    response: LLMResponse


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
        route_context = _route_context(state)
        spec_prompt = render(
            "shape_spec",
            shape=json.dumps(idea, ensure_ascii=False),
            style=json.dumps(style, ensure_ascii=False),
            route_context=json.dumps(route_context, ensure_ascii=False),
        )
        spec_response = try_complete(
            lambda: self._spec_fallback(idea),
            messages=[{"role": "user", "content": spec_prompt}],
            system=system,
            json_mode=True,
            json_schema=_SHAPE_SPEC_JSON_SCHEMA,
            temperature=0.15,
        )

        # A compatibility bridge accepts a legacy combined geometry response.
        # New providers always take the explicit semantic-specification branch.
        geometry_response: LLMResponse | None = None
        try:
            spec = _shape_spec_from_response(spec_response, idea)
        except (KeyError, TypeError, ValueError):
            if spec_response.provider != "fallback" and _looks_like_geometry_response(spec_response):
                spec = _heuristic_shape_spec(idea)
                geometry_response = spec_response
            else:
                return self._llm_fallback_shape(idea)
        if spec_response.provider == "fallback":
            return self._llm_fallback_shape(idea)

        candidate_count = _adaptive_candidate_count(spec)
        references = _reference_shape_payloads(idea)
        geometry_prompt = render(
            "shape",
            shape=json.dumps(idea, ensure_ascii=False),
            style=json.dumps(style, ensure_ascii=False),
            spec=json.dumps(asdict(spec), ensure_ascii=False, separators=(",", ":")),
            candidate_count=candidate_count,
            route_context=json.dumps(route_context, ensure_ascii=False, separators=(",", ":")),
            references=json.dumps(references, ensure_ascii=False, separators=(",", ":")),
        )
        if geometry_response is None:
            geometry_response = try_complete(
                lambda: self._llm_fallback(idea),
                messages=[{"role": "user", "content": geometry_prompt}],
                system=system,
                json_mode=True,
                json_schema=_CUSTOM_SHAPE_JSON_SCHEMA,
                temperature=0.25,
                max_tokens=4096,
            )
        if geometry_response.provider == "fallback":
            return self._llm_fallback_shape(idea)

        repair_used = False
        try:
            candidates, preferred = _candidates_from_response(
                geometry_response,
                idea=idea,
                spec=spec,
            )
        except (KeyError, TypeError, ValueError) as exc:
            repair_used = True
            repaired = self._repair_candidate(
                idea=idea,
                spec=spec,
                route_context=route_context,
                candidate_payload=_safe_response_payload(geometry_response),
                diagnostics={"geometry_errors": [" ".join(str(exc).split())[:320]]},
                system=system,
            )
            if repaired is None:
                return self._llm_fallback_shape(idea)
            candidates, preferred, geometry_response = [repaired], 0, repaired.response

        verifications, recommended = self._verify_candidates(
            idea=idea,
            spec=spec,
            candidates=candidates,
            generator_provider=geometry_response.provider,
            system=system,
        )
        selected = _select_candidate(candidates, verifications, preferred, recommended)
        selected_review = verifications.get(selected.index)

        diagnostics = _candidate_repair_diagnostics(selected, selected_review)
        threshold = get_settings().workflow.ai_shape_min_semantic_score
        semantically_weak = bool(
            selected_review
            and selected_review.independent
            and selected_review.score is not None
            and selected_review.score < threshold
        )
        if not repair_used and (diagnostics or semantically_weak):
            repaired = self._repair_candidate(
                idea=idea,
                spec=spec,
                route_context=route_context,
                candidate_payload=selected.raw,
                diagnostics=diagnostics or {"semantic_score_below": threshold},
                system=system,
            )
            if repaired is not None:
                repair_reviews, _ = self._verify_candidates(
                    idea=idea,
                    spec=spec,
                    candidates=[repaired],
                    generator_provider=repaired.response.provider,
                    system=system,
                )
                repaired_review = repair_reviews.get(repaired.index)
                if _repair_is_better(selected, selected_review, repaired, repaired_review):
                    selected, selected_review = repaired, repaired_review

        shape = selected.shape
        shape.spec = spec
        shape.recognition_features = [feature.label for feature in spec.recognition_features]
        shape.semantic_verification = selected_review
        shape.generator_provider = selected.response.provider
        shape.generator_model = selected.response.model
        shape.generator_usage = dict(selected.response.usage)
        shape.generated_candidate_count = len(candidates)
        shape.selected_candidate = selected.index
        _cache_custom_shape(cache_key, shape)
        self._record(
            state,
            (
                f"ai drawing={shape.name} candidates={len(candidates)} "
                f"semantic_score={selected_review.score if selected_review else None}"
            ),
            event="shape.ai.generated",
            generator_provider=shape.generator_provider,
            generator_model=shape.generator_model,
            verifier_provider=selected_review.provider if selected_review else None,
            verifier_independent=selected_review.independent if selected_review else False,
            semantic_score=selected_review.score if selected_review else None,
            generator_prompt_tokens=selected.response.usage.get("prompt", 0),
            generator_completion_tokens=selected.response.usage.get("completion", 0),
            verifier_prompt_tokens=(
                selected_review.usage.get("prompt", 0) if selected_review else 0
            ),
            verifier_completion_tokens=(
                selected_review.usage.get("completion", 0) if selected_review else 0
            ),
            candidate_count=len(candidates),
            repair_used=repair_used or selected is not _select_candidate(
                candidates, verifications, preferred, recommended
            ),
        )
        return shape

    def _repair_candidate(
        self,
        *,
        idea: str,
        spec: ShapeSpec,
        route_context: dict[str, object],
        candidate_payload: object,
        diagnostics: dict[str, object],
        system: str,
    ) -> _GeneratedCandidate | None:
        self.log.warning(
            "AI shape candidate needs one bounded targeted repair: %s",
            json.dumps(diagnostics, ensure_ascii=False)[:480],
        )
        repair_prompt = render(
            "shape_repair",
            shape=json.dumps(idea, ensure_ascii=False),
            spec=json.dumps(asdict(spec), ensure_ascii=False, separators=(",", ":")),
            candidate=json.dumps(candidate_payload, ensure_ascii=False, separators=(",", ":"))[:12000],
            diagnostics=json.dumps(diagnostics, ensure_ascii=False, separators=(",", ":")),
            route_context=json.dumps(route_context, ensure_ascii=False, separators=(",", ":")),
        )
        repaired = try_complete(
            lambda: self._llm_fallback(idea),
            messages=[{"role": "user", "content": repair_prompt}],
            system=system,
            json_mode=True,
            json_schema=_SHAPE_REPAIR_JSON_SCHEMA,
            temperature=0.15,
            max_tokens=3072,
        )
        if repaired.provider == "fallback":
            return None
        try:
            data = extract_json(repaired.text)
            raw = data.get("candidate") if isinstance(data, dict) else None
            if isinstance(raw, dict) and "program" in raw:
                return _candidate_from_program(raw, 0, idea, spec, repaired)
            # Compatibility for a provider that returned legacy geometry.
            legacy_shape = _shape_from_response(repaired, idea)
            return _GeneratedCandidate(0, "legacy repair", {}, legacy_shape, 0.5, [], repaired)
        except (KeyError, TypeError, ValueError):
            return None

    def _verify_candidates(
        self,
        *,
        idea: str,
        spec: ShapeSpec,
        candidates: list[_GeneratedCandidate],
        generator_provider: str,
        system: str,
    ) -> tuple[dict[int, ShapeVerification], int | None]:
        deterministic = {
            candidate.index: _geometry_only_verification(candidate)
            for candidate in candidates
        }
        if (
            not get_settings().workflow.ai_shape_verifier_enabled
            or not candidates
            or any("program" not in candidate.raw for candidate in candidates)
        ):
            return deterministic, None
        images = [
            ImageInput(
                shape_program.render_paths_png_data_url(
                    _final_ai_preview_paths(candidate.shape.paths, candidate.shape.closed)
                ),
                detail="high",
            )
            for candidate in candidates
        ]
        prompt = render(
            "shape_verify",
            shape=json.dumps(idea, ensure_ascii=False),
            spec=json.dumps(asdict(spec), ensure_ascii=False, separators=(",", ":")),
        )
        response = try_complete(
            lambda: LLMResponse(text="{}", provider="fallback", model="geometry-checks"),
            messages=[{"role": "user", "content": prompt}],
            system=system,
            images=images,
            json_mode=True,
            json_schema=_SHAPE_VERIFICATION_JSON_SCHEMA,
            temperature=0,
            max_tokens=2048,
            exclude_provider=generator_provider,
            pin_provider=False,
        )
        independent = response.provider not in {"fallback", generator_provider}
        if not independent:
            return deterministic, None
        try:
            reviews, recommended = _verifications_from_response(response, candidates, spec)
        except (KeyError, TypeError, ValueError):
            return deterministic, None
        return reviews, recommended

    def _spec_fallback(self, idea: str) -> LLMResponse:
        return LLMResponse(
            text=json.dumps(asdict(_heuristic_shape_spec(idea))),
            provider="fallback",
            model="rules",
        )

    def _llm_fallback(self, idea: str) -> LLMResponse:
        fallback = _label_fallback_shape(idea)
        payload = {
            "name": fallback.name,
            "recognition_features": [
                "large readable label outline",
                "balanced width and height",
                "continuous route-friendly stroke",
            ],
            "variants": [
                {
                    "paths": [[[x, y] for x, y in path] for path in fallback.paths],
                    "closed": fallback.closed,
                },
                {
                    "paths": [[[x, y] for x, y in path] for path in fallback.paths],
                    "closed": fallback.closed,
                },
            ],
            "preferred_variant": 0,
        }
        return LLMResponse(text=json.dumps(payload), provider="fallback", model="rules")

    def _llm_fallback_shape(self, idea: str) -> Shape:
        return _label_fallback_shape(idea)


def _shape_spec_from_response(resp: LLMResponse, idea: str) -> ShapeSpec:
    data = extract_json(resp.text)
    if not isinstance(data, dict):
        raise ValueError("ShapeSpec response must be an object")
    subject = _clean_text(data.get("subject"), max_length=80)
    modifiers = _clean_text_list(data.get("modifiers"), maximum=6, allow_empty=True)
    pose = _clean_text(data.get("pose"), max_length=120, allow_empty=True)
    viewpoint = data.get("viewpoint")
    if viewpoint not in {"front", "side", "three-quarter", "symbolic", "unspecified"}:
        raise ValueError("ShapeSpec has an invalid viewpoint")
    raw_parts = data.get("parts")
    if not isinstance(raw_parts, list) or not 2 <= len(raw_parts) <= 10:
        raise ValueError("ShapeSpec needs two to ten parts")
    parts: list[ShapePart] = []
    part_ids: set[str] = set()
    for raw in raw_parts:
        if not isinstance(raw, dict):
            raise ValueError("ShapeSpec parts must be objects")
        part_id = _semantic_id(raw.get("id"))
        if part_id in part_ids:
            raise ValueError("ShapeSpec part ids must be unique")
        parent = raw.get("parent")
        if parent is not None:
            parent = _semantic_id(parent)
        relative_size = raw.get("relative_size")
        if relative_size not in {"small", "medium", "large", "dominant"}:
            raise ValueError("ShapeSpec part has invalid relative_size")
        if not isinstance(raw.get("required"), bool):
            raise ValueError("ShapeSpec part required flag must be boolean")
        parts.append(
            ShapePart(
                id=part_id,
                label=_clean_text(raw.get("label"), max_length=80),
                parent=parent,
                required=raw["required"],
                relative_size=relative_size,
                position=_clean_text(raw.get("position"), max_length=120, allow_empty=True),
            )
        )
        part_ids.add(part_id)
    if any(part.parent is not None and part.parent not in part_ids for part in parts):
        raise ValueError("ShapeSpec part parent must reference another part")

    raw_features = data.get("recognition_features")
    if not isinstance(raw_features, list) or not 3 <= len(raw_features) <= 6:
        raise ValueError("ShapeSpec needs three to six recognition features")
    features: list[ShapeFeature] = []
    feature_ids: set[str] = set()
    for raw in raw_features:
        if not isinstance(raw, dict):
            raise ValueError("ShapeSpec recognition features must be objects")
        feature_id = _semantic_id(raw.get("id"))
        importance = raw.get("importance")
        if isinstance(importance, bool) or not isinstance(importance, int) or not 1 <= importance <= 5:
            raise ValueError("recognition feature importance must be 1 to 5")
        if feature_id in feature_ids:
            raise ValueError("recognition feature ids must be unique")
        features.append(
            ShapeFeature(
                id=feature_id,
                label=_clean_text(raw.get("label"), max_length=120),
                importance=importance,
                geometry_hint=_clean_text(raw.get("geometry_hint"), max_length=160, allow_empty=True),
                relation=_clean_text(raw.get("relation"), max_length=160, allow_empty=True),
            )
        )
        feature_ids.add(feature_id)
    symmetry = data.get("symmetry")
    if symmetry not in {"none", "approximate", "bilateral", "radial"}:
        raise ValueError("ShapeSpec has invalid symmetry")
    preferred_strokes = data.get("preferred_strokes")
    if isinstance(preferred_strokes, bool) or not isinstance(preferred_strokes, int) or not 1 <= preferred_strokes <= 4:
        raise ValueError("ShapeSpec preferred_strokes must be 1 to 4")
    if not isinstance(data.get("closed_silhouette"), bool):
        raise ValueError("ShapeSpec closed_silhouette must be boolean")
    aspect_ratio = _bounded_float(data.get("aspect_ratio"), 0.5, 2.0, "aspect_ratio")
    ambiguity = _bounded_float(data.get("ambiguity"), 0.0, 1.0, "ambiguity")
    return ShapeSpec(
        subject=subject or " ".join(idea.split())[:80],
        modifiers=modifiers,
        pose=pose,
        viewpoint=viewpoint,
        parts=parts,
        recognition_features=features,
        symmetry=symmetry,
        preferred_strokes=preferred_strokes,
        closed_silhouette=data["closed_silhouette"],
        aspect_ratio=aspect_ratio,
        ambiguity=ambiguity,
    )


def _heuristic_shape_spec(idea: str) -> ShapeSpec:
    subject = " ".join(idea.split())[:80] or "custom shape"
    return ShapeSpec(
        subject=subject,
        modifiers=[],
        pose="as requested",
        viewpoint="unspecified",
        parts=[
            ShapePart("main_body", "main body", None, True, "dominant", "centre"),
            ShapePart("identity_cue", "distinctive outer feature", "main_body", True, "medium", "on outer contour"),
        ],
        recognition_features=[
            ShapeFeature("overall_silhouette", "recognisable overall silhouette", 5, "broad outer contour", "contains all parts"),
            ShapeFeature("main_body_mass", "clear main body mass", 4, "large central interval", "anchors the silhouette"),
            ShapeFeature("distinctive_feature", "request-specific distinguishing feature", 5, "large separated contour interval", "attached to the main body"),
        ],
        symmetry="approximate",
        preferred_strokes=1,
        closed_silhouette=True,
        aspect_ratio=1.0,
        ambiguity=0.65,
    )


def _adaptive_candidate_count(spec: ShapeSpec) -> int:
    complexity = len(spec.parts) + len(spec.modifiers) + sum(
        bool(feature.relation.strip()) for feature in spec.recognition_features
    )
    count = 2
    if spec.ambiguity >= 0.35 or complexity >= 9:
        count += 1
    if spec.ambiguity >= 0.72 or complexity >= 13:
        count += 1
    return min(max(2, get_settings().workflow.ai_shape_max_candidates), count)


def _candidates_from_response(
    resp: LLMResponse,
    *,
    idea: str,
    spec: ShapeSpec,
) -> tuple[list[_GeneratedCandidate], int]:
    data = extract_json(resp.text)
    if not isinstance(data, dict):
        raise ValueError("geometry response must be an object")
    variants = data.get("variants")
    if not isinstance(variants, list) or not variants:
        # Compatibility with the pre-program point-list format.
        legacy = _shape_from_geometry(data, idea=idea, source="llm")
        return [_GeneratedCandidate(0, "legacy points", data, legacy, 0.5, [], resp)], 0
    if all(isinstance(variant, dict) and "program" not in variant for variant in variants):
        legacy = _best_shape_variant(data, idea=idea, source="llm")
        return [_GeneratedCandidate(0, "legacy alternatives", data, legacy, 0.5, [], resp)], 0
    if not 2 <= len(variants) <= 4:
        raise ValueError("geometry response needs two to four candidates")
    preferred = data.get("preferred_variant")
    if isinstance(preferred, bool) or not isinstance(preferred, int) or not 0 <= preferred < len(variants):
        raise ValueError("preferred_variant does not select a candidate")
    candidates: list[_GeneratedCandidate] = []
    errors: list[str] = []
    for index, raw in enumerate(variants):
        if not isinstance(raw, dict):
            errors.append(f"candidate {index}: not an object")
            continue
        try:
            candidate = _candidate_from_program(raw, index, idea, spec, resp)
            if any(
                shape_uniqueness.contour_distance(candidate.shape.paths, other.shape.paths) <= 0.035
                for other in candidates
            ):
                raise ValueError("duplicates another generated candidate")
            candidates.append(candidate)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"candidate {index}: {exc}")
    if not candidates:
        raise ValueError("; ".join(errors)[:640] or "no valid drawing candidate")
    return candidates, preferred


def _candidate_from_program(
    raw: dict,
    index: int,
    idea: str,
    spec: ShapeSpec,
    response: LLMResponse,
) -> _GeneratedCandidate:
    strategy = _clean_text(raw.get("strategy"), max_length=120)
    required_ids = {feature.id for feature in spec.recognition_features}
    compiled = shape_program.compile_shape_program(
        raw.get("program"),
        required_feature_ids=required_ids,
    )
    _validate_route_friendly_geometry(compiled.paths)
    _validate_shape_spec_geometry(compiled, spec)
    _validate_distinct_custom_geometry(compiled.paths)
    shape = Shape(
        name=" ".join(idea.split())[:80],
        paths=compiled.paths,
        closed=compiled.closed,
        source="llm",
    )
    return _GeneratedCandidate(
        index=index,
        strategy=strategy,
        raw=raw,
        shape=shape,
        local_score=shape_program.local_program_score(compiled, required_ids),
        feature_warnings=compiled.warnings,
        response=response,
    )


def _geometry_only_verification(candidate: _GeneratedCandidate) -> ShapeVerification:
    missing = [
        warning.removeprefix("missing feature spans: ")
        for warning in candidate.feature_warnings
        if warning.startswith("missing feature spans:")
    ]
    return ShapeVerification(
        score=None,
        subject_match=None,
        silhouette_quality=candidate.local_score,
        route_readability=candidate.local_score,
        missing_features=[item for group in missing for item in group.split(", ")],
        repair_instructions=list(candidate.feature_warnings),
        independent=False,
        method="geometry",
    )


def _verifications_from_response(
    resp: LLMResponse,
    candidates: list[_GeneratedCandidate],
    spec: ShapeSpec,
) -> tuple[dict[int, ShapeVerification], int | None]:
    data = extract_json(resp.text)
    if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
        raise ValueError("visual verifier response needs reviews")
    candidate_ids = {candidate.index for candidate in candidates}
    reviews: dict[int, ShapeVerification] = {}
    expected_features = {feature.id: feature for feature in spec.recognition_features}
    for raw in data["reviews"]:
        if not isinstance(raw, dict):
            raise ValueError("visual review must be an object")
        index = raw.get("candidate_index")
        if isinstance(index, bool) or not isinstance(index, int) or index not in candidate_ids:
            raise ValueError("visual review references an unknown candidate")
        cues: list[ShapeCueVerification] = []
        if not isinstance(raw.get("cue_results"), list):
            raise ValueError("visual review cue_results must be an array")
        for cue in raw["cue_results"]:
            if not isinstance(cue, dict) or not isinstance(cue.get("present"), bool):
                raise ValueError("invalid visual cue result")
            cues.append(
                ShapeCueVerification(
                    feature_id=_semantic_id(cue.get("feature_id")),
                    present=cue["present"],
                    score=_bounded_float(cue.get("score"), 0, 1, "cue score"),
                    reason=_clean_text(cue.get("reason"), max_length=180, allow_empty=True),
                )
            )
        if {cue.feature_id for cue in cues} != set(expected_features):
            raise ValueError("visual review must score every required cue exactly once")
        cue_score = sum(
            cue.score * expected_features[cue.feature_id].importance
            for cue in cues
        ) / sum(feature.importance for feature in expected_features.values())
        subject_match = _bounded_float(raw.get("subject_match"), 0, 1, "subject_match")
        silhouette_quality = _bounded_float(raw.get("silhouette_quality"), 0, 1, "silhouette_quality")
        route_readability = _bounded_float(raw.get("route_readability"), 0, 1, "route_readability")
        calculated_score = (
            0.45 * cue_score
            + 0.25 * subject_match
            + 0.15 * silhouette_quality
            + 0.15 * route_readability
        )
        reported_score = _bounded_float(raw.get("score"), 0, 1, "semantic score")
        reviews[index] = ShapeVerification(
            score=min(reported_score, calculated_score),
            subject_match=subject_match,
            silhouette_quality=silhouette_quality,
            route_readability=route_readability,
            cue_results=cues,
            missing_features=_clean_text_list(raw.get("missing_features"), maximum=6, allow_empty=True),
            wrong_relations=_clean_text_list(raw.get("wrong_relations"), maximum=6, allow_empty=True),
            repair_instructions=_clean_text_list(raw.get("repair_instructions"), maximum=6, allow_empty=True),
            provider=resp.provider,
            model=resp.model,
            independent=True,
            method="rendered-image",
            usage=dict(resp.usage),
        )
    for candidate in candidates:
        reviews.setdefault(candidate.index, _geometry_only_verification(candidate))
    recommended = data.get("recommended_candidate")
    if isinstance(recommended, bool) or not isinstance(recommended, int) or recommended not in candidate_ids:
        recommended = None
    return reviews, recommended


def _select_candidate(
    candidates: list[_GeneratedCandidate],
    reviews: dict[int, ShapeVerification],
    preferred: int,
    recommended: int | None,
) -> _GeneratedCandidate:
    def score(candidate: _GeneratedCandidate) -> tuple[float, float, float]:
        review = reviews.get(candidate.index)
        semantic = (
            review.score
            if review and review.independent and review.score is not None
            else candidate.local_score
        )
        return (
            semantic,
            1.0 if candidate.index == recommended else 0.0,
            1.0 if candidate.index == preferred else 0.0,
        )

    return max(candidates, key=score)


def _candidate_repair_diagnostics(
    candidate: _GeneratedCandidate,
    review: ShapeVerification | None,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {}
    if candidate.feature_warnings:
        diagnostics["feature_coverage"] = candidate.feature_warnings
    if review and review.independent:
        if review.missing_features:
            diagnostics["missing_features"] = review.missing_features
        if review.wrong_relations:
            diagnostics["wrong_relations"] = review.wrong_relations
        if review.repair_instructions:
            diagnostics["repair_instructions"] = review.repair_instructions
    return diagnostics


def _repair_is_better(
    original: _GeneratedCandidate,
    original_review: ShapeVerification | None,
    repaired: _GeneratedCandidate,
    repaired_review: ShapeVerification | None,
) -> bool:
    if repaired.feature_warnings and not original.feature_warnings:
        return False
    if repaired_review and repaired_review.independent and repaired_review.score is not None:
        baseline = (
            original_review.score
            if original_review and original_review.independent and original_review.score is not None
            else original.local_score
        )
        return repaired_review.score >= baseline + 0.02
    return len(repaired.feature_warnings) < len(original.feature_warnings)


def _route_context(state: WorkflowState) -> dict[str, object]:
    intent = state.intent
    plan = state.plan
    return {
        "sport": intent.sport if intent else None,
        "target_distance_km": intent.distance_km if intent else None,
        "city": intent.city if intent else None,
        "difficulty": plan.difficulty if plan else None,
        "placement_hints": plan.placement_hints if plan else None,
    }


def _validate_shape_spec_geometry(
    compiled: shape_program.CompiledShapeProgram,
    spec: ShapeSpec,
) -> None:
    if spec.closed_silhouette and not compiled.closed:
        raise ValueError("ShapeSpec requires a closed outer silhouette")
    if len(compiled.paths) > max(2, spec.preferred_strokes + 1):
        raise ValueError("drawing uses too many strokes for its ShapeSpec")
    points = [point for path in compiled.paths for point in path]
    width = max(point[0] for point in points) - min(point[0] for point in points)
    height = max(point[1] for point in points) - min(point[1] for point in points)
    actual_ratio = width / max(height, 1e-9)
    ratio_error = max(actual_ratio / spec.aspect_ratio, spec.aspect_ratio / actual_ratio)
    if ratio_error > 2.25:
        raise ValueError("drawing aspect ratio conflicts with its ShapeSpec")
    for feature in spec.recognition_features:
        minimum = 0.05 if feature.importance >= 4 else 0.03
        coverage = compiled.feature_coverage.get(feature.id, 0.0)
        if 0 < coverage < minimum:
            compiled.warnings.append(
                f"feature {feature.id} covers {coverage:.1%}; enlarge it to at least {minimum:.0%}"
            )


def _final_ai_preview_paths(paths: list[geo.Path], closed: bool) -> list[geo.Path]:
    """Mirror the exact smoothing/normalisation applied after candidate choice."""

    smoothed: list[geo.Path] = []
    for path in paths:
        candidate = geo.catmull_rom_smooth(
            path,
            closed=closed,
            subdivisions=3,
            corner_threshold_deg=70.0,
        )
        smoothed.append(candidate if _is_simple_path(candidate) else list(path))
    return geo.normalize_shape(smoothed)


def _looks_like_geometry_response(resp: LLMResponse) -> bool:
    try:
        data = extract_json(resp.text)
    except (TypeError, ValueError):
        return False
    return isinstance(data, dict) and ("paths" in data or "variants" in data)


def _safe_response_payload(resp: LLMResponse) -> object:
    try:
        return extract_json(resp.text)
    except (TypeError, ValueError):
        return {"invalid_response": resp.text[:1200]}


def _clean_text(value: object, *, max_length: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("expected text")
    cleaned = " ".join(value.split())[:max_length]
    if not cleaned and not allow_empty:
        raise ValueError("text value cannot be empty")
    return cleaned


def _clean_text_list(value: object, *, maximum: int, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or (not value and not allow_empty):
        raise ValueError("expected a bounded text array")
    return [_clean_text(item, max_length=180) for item in value]


def _semantic_id(value: object) -> str:
    identifier = _clean_text(value, max_length=48)
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", identifier):
        raise ValueError("semantic ids must be lowercase ASCII identifiers")
    return identifier


def _bounded_float(value: object, minimum: float, maximum: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a number")
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise ValueError(f"{label} must stay between {minimum} and {maximum}")
    return parsed


def _shape_from_response(resp: LLMResponse, idea: str) -> Shape:
    data = extract_json(resp.text)
    if not isinstance(data, dict):
        raise ValueError("response must be a JSON object")
    source = "fallback" if resp.provider == "fallback" else "llm"
    if isinstance(data.get("variants"), list):
        return _best_shape_variant(data, idea=idea, source=source)

    # Backwards-compatible parsing for cached/test responses and providers that
    # briefly return the pre-v4 object despite receiving the strict schema.
    return _shape_from_geometry(data, idea=idea, source=source)


def _best_shape_variant(data: dict, *, idea: str, source: str) -> Shape:
    _validated_recognition_features(data.get("recognition_features"))
    variants = data.get("variants")
    if not isinstance(variants, list) or len(variants) != 2:
        raise ValueError("exactly two alternative silhouettes are required")

    preferred = data.get("preferred_variant")
    if isinstance(preferred, bool) or not isinstance(preferred, int) or preferred not in {0, 1}:
        raise ValueError("preferred_variant must select alternative 0 or 1")

    reasons: list[str] = []
    for index in (preferred, 1 - preferred):
        raw_variant = variants[index]
        if not isinstance(raw_variant, dict):
            reasons.append(f"alternative {index + 1} is not an object")
            continue
        try:
            return _shape_from_geometry(raw_variant, idea=idea, source=source)
        except (KeyError, TypeError, ValueError) as exc:
            reasons.append(f"alternative {index + 1}: {exc}")

    raise ValueError("; ".join(reasons)[:480] or "no valid alternative silhouette")


def _shape_from_geometry(data: dict, *, idea: str, source: str) -> Shape:
    closed = _parse_bool(data.get("closed", False))
    paths = _validated_paths(data.get("paths"), closed=closed)
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


def _validated_recognition_features(value: object) -> list[str]:
    """Require a compact, non-duplicated semantic brief before accepting variants."""

    if not isinstance(value, list) or not 3 <= len(value) <= 6:
        raise ValueError("the silhouette needs three to six recognition features")
    features: list[str] = []
    seen: set[str] = set()
    for raw_feature in value:
        if not isinstance(raw_feature, str):
            raise ValueError("every recognition feature must be text")
        feature = " ".join(raw_feature.split())[:120]
        key = feature.casefold()
        if len(feature) < 4 or key in seen:
            raise ValueError("recognition features must be meaningful and distinct")
        seen.add(key)
        features.append(feature)
    return features


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
    """Render the described words when semantic outline generation is unavailable."""

    ascii_idea = unicodedata.normalize("NFKD", idea).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", ascii_idea)
    if words:
        label = " ".join(words).upper()
        paths, closed = text_shapes.text_to_shape(label)
        if any(len(path) >= 2 for path in paths):
            return Shape(
                name=f"text:{label}",
                paths=[list(path) for path in paths],
                closed=closed,
                source="fallback",
            )

    name, paths, closed = shape_library.star()
    return Shape(name=name, paths=[list(path) for path in paths], closed=closed, source="fallback")


def _reference_shape_payloads(idea: str, *, limit: int = 3) -> list[dict[str, object]]:
    """Return ordered subject/accessory anchors for a compound request."""

    low = idea.casefold()
    matches: list[tuple[int, int, str]] = []
    for keyword, canonical_name in shape_library.KEYWORDS.items():
        match = re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", low)
        if match:
            matches.append((match.start(), -len(keyword), canonical_name))
    payloads: list[dict[str, object]] = []
    seen: set[str] = set()
    for _, _, canonical_name in sorted(matches):
        if canonical_name in seen:
            continue
        hit = shape_library.get_shape(canonical_name)
        if hit is None:
            continue
        name, generated_paths, closed = hit
        authored = shape_library.AUTHORED_OUTLINES.get(name)
        reference_paths = (
            [list(authored)]
            if authored
            else [_sample_reference_path(path) for path in generated_paths[:4]]
        )
        payloads.append(
            {
                "role": "primary_subject" if not payloads else "related_part",
                "name": name,
                "paths": reference_paths,
                "closed": closed,
            }
        )
        seen.add(canonical_name)
        if len(payloads) >= limit:
            break
    return payloads


def _reference_shape_payload(idea: str) -> dict[str, object] | None:
    """Find the earliest catalogued subject in a compound free-text request.

    The reference is prompt context, not the result: the AI still has to make
    requested poses, accessories, and relationships visible. Giving it a
    recognisable base contour prevents a known subject from losing its anatomy
    while those custom details are added.
    """

    payloads = _reference_shape_payloads(idea, limit=1)
    if not payloads:
        return None
    payload = dict(payloads[0])
    payload.pop("role", None)
    return payload


def _sample_reference_path(path: geo.Path, max_points: int = 48) -> geo.Path:
    """Keep prompt reference geometry compact without losing its endpoints."""

    if len(path) <= max_points:
        return list(path)
    is_closed = len(path) >= 3 and path[0] == path[-1]
    core = path[:-1] if is_closed else path
    target = max_points - 1 if is_closed else max_points
    indices = [round(index * (len(core) - 1) / (target - 1)) for index in range(target)]
    sampled = [core[index] for index in indices]
    if is_closed:
        sampled.append(sampled[0])
    return sampled


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
    return deepcopy(shape)


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if isinstance(value, int | float):
        return value == 1
    return False
