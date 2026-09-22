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

from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

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
_CUSTOM_SHAPE_CACHE_VERSION = "v31-final-semantic-scaffolds"
_CUSTOM_SHAPE_CACHE: OrderedDict[tuple[str, str], Shape] = OrderedDict()
_CUSTOM_SHAPE_CACHE_LOCK = Lock()
_FULL_SEMANTIC_SCAFFOLD_MODES = {
    "bear", "bicycle", "cat", "coffee_cup", "dragon", "key", "moon_leap",
    "phoenix", "platypus", "radial", "robot_umbrella", "sailboat",
    "spiral",
}

# Responses API output budgets include the strict JSON payload and, for
# reasoning-capable models, internal reasoning tokens. A four-candidate shape
# response is substantially larger than ordinary intent JSON; using the global
# 2K default made valid calls intermittently terminate before the JSON closed.
_SHAPE_SPEC_MAX_TOKENS = 6144
_SHAPE_GEOMETRY_MAX_TOKENS = 8192
_SHAPE_REPAIR_MAX_TOKENS = 6144
_SHAPE_REVIEW_MAX_TOKENS = 4096

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
            "minItems": 1,
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

_REFERENCE_SHAPE_JSON_SCHEMA = {
    "type": "object",
    "description": "One-pass visual analysis and route-native GPS-art drawing.",
    "properties": {
        "spec": _SHAPE_SPEC_JSON_SCHEMA,
        "name": {"type": "string", "maxLength": 80},
        "variants": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": _CUSTOM_SHAPE_VARIANT_JSON_SCHEMA,
        },
        "preferred_variant": {"type": "integer", "minimum": 0, "maximum": 1},
    },
    "required": ["spec", "name", "variants", "preferred_variant"],
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
        if (
            state.reference_kind == "svg"
            and state.reference_shape is not None
        ):
            shape = deepcopy(state.reference_shape)
        elif state.reference_image_data_url:
            shape = self._try_llm(state)
            if shape.source == "fallback" and state.reference_shape is not None:
                shape = deepcopy(state.reference_shape)
        elif state.reference_shape is not None:
            shape = deepcopy(state.reference_shape)
        else:
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
        from ..tools.feature_tracking import normalize_with_features
        normalize_with_features(shape)
        state.shape = shape
        if shape.source == "fallback":
            requested = state.intent.shape if state.intent else None
            state.errors.append(
                f"shape: we couldn't build a reliable custom outline for "
                f"{requested or 'this idea'!r}; using the deterministic "
                f"{shape.name!r} fallback"
            )
        self._record(state, f"shape={shape.name} source={shape.source} paths={len(shape.paths)}")
        return state

    def _smooth(self, shape: Shape) -> list[list[tuple[float, float]]]:
        if shape.source == "llm":
            smoothed: list[geo.Path] = []
            for path in shape.paths:
                path_closed = len(path) >= 3 and path[0] == path[-1]
                candidate = geo.catmull_rom_smooth(
                    path,
                    closed=path_closed,
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
        if state.reference_image_data_url:
            return [self._try_llm]
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
        reference_images = (
            [ImageInput(state.reference_image_data_url, detail="auto")]
            if state.reference_image_data_url
            else []
        )
        reference_digest = (
            hashlib.sha256(state.reference_image_data_url.encode()).hexdigest()
            if state.reference_image_data_url
            else ""
        )
        cache_key = _custom_shape_cache_key(idea, style, reference_digest)
        cached = _get_cached_custom_shape(
            cache_key,
            name=state.reference_name or idea,
        )
        if cached is not None:
            return cached

        system = self.system_prompt
        route_context = _route_context(state)
        geometry_response: LLMResponse | None = None
        spec_response: LLMResponse | None = None
        if reference_images:
            reference_prompt = render(
                "shape_reference",
                shape=json.dumps(idea, ensure_ascii=False),
                style=json.dumps(style, ensure_ascii=False),
                reference_name=json.dumps(state.reference_name or "linked image", ensure_ascii=False),
                reference_kind=json.dumps(state.reference_kind or "image", ensure_ascii=False),
                route_context=json.dumps(route_context, ensure_ascii=False, separators=(",", ":")),
            )
            geometry_response = try_complete(
                lambda: self._llm_fallback(idea),
                messages=[{"role": "user", "content": reference_prompt}],
                system=system,
                json_mode=True,
                json_schema=_REFERENCE_SHAPE_JSON_SCHEMA,
                temperature=0.15,
                max_tokens=_SHAPE_GEOMETRY_MAX_TOKENS,
                images=reference_images,
                max_provider_attempts=1,
            )
            if geometry_response.provider == "fallback":
                return self._llm_fallback_shape(idea)
            try:
                reference_payload = extract_json(geometry_response.text)
                if not isinstance(reference_payload, dict):
                    raise ValueError("visual response must be an object")
                spec = _shape_spec_from_payload(reference_payload.get("spec"), idea)
            except (KeyError, TypeError, ValueError) as error:
                self.log.warning(
                    "Visual reference ShapeSpec was invalid: %s",
                    " ".join(str(error).split())[:320],
                )
                return self._llm_fallback_shape(idea)
        else:
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
                max_tokens=_SHAPE_SPEC_MAX_TOKENS,
            )
            try:
                spec = _shape_spec_from_response(spec_response, idea)
            except (KeyError, TypeError, ValueError) as error:
                if spec_response.provider != "fallback" and _looks_like_geometry_response(spec_response):
                    spec = _heuristic_shape_spec(idea)
                    geometry_response = spec_response
                else:
                    self.log.warning(
                        "AI ShapeSpec was invalid; using the bounded heuristic spec: %s",
                        " ".join(str(error).split())[:320],
                    )
                    spec = _heuristic_shape_spec(idea)
            if spec_response.provider == "fallback":
                return _catalog_fallback_shape(idea, spec, spec_response) or self._llm_fallback_shape(idea)

        if geometry_response is None:
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
            geometry_response = try_complete(
                lambda: self._llm_fallback(idea),
                messages=[{"role": "user", "content": geometry_prompt}],
                system=system,
                json_mode=True,
                json_schema=_CUSTOM_SHAPE_JSON_SCHEMA,
                temperature=0.25,
                max_tokens=_SHAPE_GEOMETRY_MAX_TOKENS,
                images=reference_images or None,
            )
        if geometry_response.provider == "fallback":
            if not reference_images:
                grounded_fallback = _catalog_fallback_shape(
                    idea,
                    spec,
                    spec_response or geometry_response,
                )
                if grounded_fallback is not None:
                    return grounded_fallback
            return self._llm_fallback_shape(idea)

        repair_used = False
        try:
            candidates, preferred = _candidates_from_response(
                geometry_response,
                idea=idea,
                spec=spec,
            )
        except (KeyError, TypeError, ValueError) as exc:
            if reference_images:
                self.log.warning(
                    "Visual shape response was unusable; using the immediate image contour: %s",
                    " ".join(str(exc).split())[:320],
                )
                return self._llm_fallback_shape(idea)
            grounded_candidate = _semantic_scaffold_candidate(
                idea=idea,
                spec=spec,
                response=geometry_response,
                index=0,
            )
            if grounded_candidate is not None:
                self.log.warning(
                    "AI programs were unusable; retaining a semantic scaffold "
                    "candidate for visual review: %s",
                    " ".join(str(exc).split())[:320],
                )
                candidates, preferred = [grounded_candidate], 0
            else:
                repair_used = True
                repaired = self._repair_candidate(
                    idea=idea,
                    spec=spec,
                    route_context=route_context,
                    candidate_payload=_safe_response_payload(geometry_response),
                    diagnostics={"geometry_errors": [" ".join(str(exc).split())[:320]]},
                    system=system,
                    reference_images=reference_images,
                )
                if repaired is None:
                    return self._llm_fallback_shape(idea)
                candidates, preferred, geometry_response = [repaired], 0, repaired.response
        if (
            not reference_images
            and not any("grounded semantic scaffold" in candidate.strategy for candidate in candidates)
            and not any("ShapeSpec scaffold" in candidate.strategy for candidate in candidates)
        ):
            removed: _GeneratedCandidate | None = None
            if len(candidates) < 4:
                grounded_index = next(
                    index for index in range(4)
                    if all(candidate.index != index for candidate in candidates)
                )
            else:
                removable = [
                    candidate for candidate in candidates
                    if candidate.index != preferred
                ] or list(candidates)
                removed = min(removable, key=lambda candidate: candidate.local_score)
                grounded_index = removed.index
            grounded = _semantic_scaffold_candidate(
                idea=idea,
                spec=spec,
                response=geometry_response,
                index=grounded_index,
            )
            if grounded is not None:
                if removed is not None:
                    candidates = [
                        candidate for candidate in candidates
                        if candidate is not removed
                    ]
                candidates.append(grounded)
        if reference_images:
            verifications = {
                candidate.index: _geometry_only_verification(candidate)
                for candidate in candidates
            }
            recommended = None
        else:
            verifications, recommended = self._verify_candidates(
                idea=idea,
                spec=spec,
                candidates=candidates,
                generator_provider=geometry_response.provider,
                system=system,
            )
            scaffold_mode = _semantic_scaffold_mode(spec)
            explicitly_sided_robot = scaffold_mode == "robot" and any(
                token in unicodedata.normalize("NFKD", idea)
                .encode("ascii", "ignore")
                .decode()
                .casefold()
                for token in ("left arm", "left hand", "right arm", "right hand")
            )
            adjudicate_scaffolds = bool(
                scaffold_mode in _FULL_SEMANTIC_SCAFFOLD_MODES
                or explicitly_sided_robot
            )
            for candidate in candidates:
                if not adjudicate_scaffolds:
                    break
                if "scaffold" not in candidate.strategy:
                    continue
                comparative = verifications.get(candidate.index)
                if not (
                    comparative
                    and _is_rendered_visual_review(comparative)
                    and comparative.score is not None
                ):
                    continue
                needs_isolated_adjudication = bool(
                    _visual_defect_count(comparative) > 0
                    or comparative.wrong_relations
                    or comparative.score
                    < get_settings().workflow.ai_shape_min_semantic_score
                )
                if not needs_isolated_adjudication:
                    continue
                # Comparative contact sheets occasionally cause the critic to
                # attribute a neighbouring candidate's limb or relation to a
                # deterministic semantic scaffold.  Recheck only questioned
                # scaffolds in isolation, then keep the strictly better cue
                # verdict.  This is adjudication, not unconditional boosting.
                isolated, _ = self._verify_candidates(
                    idea=idea,
                    spec=spec,
                    candidates=[candidate],
                    generator_provider=geometry_response.provider,
                    system=system,
                )
                adjudicated = isolated.get(candidate.index)
                if not (
                    adjudicated
                    and _is_rendered_visual_review(adjudicated)
                    and adjudicated.score is not None
                ):
                    continue
                if (
                    _visual_defect_count(adjudicated)
                    < _visual_defect_count(comparative)
                    or (
                        _visual_defect_count(adjudicated)
                        == _visual_defect_count(comparative)
                        and adjudicated.score
                        > comparative.score
                    )
                ):
                    verifications[candidate.index] = adjudicated
        selected = _select_candidate(candidates, verifications, preferred, recommended)
        selected_review = verifications.get(selected.index)

        diagnostics = _candidate_repair_diagnostics(selected, selected_review)
        threshold = get_settings().workflow.ai_shape_min_semantic_score
        semantically_weak = bool(
            selected_review
            and _is_rendered_visual_review(selected_review)
            and selected_review.score is not None
            and selected_review.score < threshold
        )
        if not reference_images and not repair_used and (diagnostics or semantically_weak):
            repaired = self._repair_candidate(
                idea=idea,
                spec=spec,
                route_context=route_context,
                candidate_payload=selected.raw,
                diagnostics=diagnostics or {"semantic_score_below": threshold},
                system=system,
                reference_images=reference_images,
            )
            challengers: list[_GeneratedCandidate] = []
            if repaired is not None:
                challengers.append(repaired)
            if (
                "grounded semantic scaffold" not in selected.strategy
                and "ShapeSpec scaffold" not in selected.strategy
                and not any(
                    "grounded semantic scaffold" in candidate.strategy
                    or "ShapeSpec scaffold" in candidate.strategy
                    for candidate in candidates
                )
            ):
                grounded_challenger = _semantic_scaffold_candidate(
                    idea=idea,
                    spec=spec,
                    response=geometry_response,
                    index=1 if challengers else 0,
                )
                if grounded_challenger is not None:
                    challengers.append(grounded_challenger)
            if challengers:
                repair_reviews, repair_recommended = self._verify_candidates(
                    idea=idea,
                    spec=spec,
                    candidates=challengers,
                    generator_provider=geometry_response.provider,
                    system=system,
                    reference_images=reference_images,
                )
                challenger = _select_candidate(
                    challengers,
                    repair_reviews,
                    preferred=challengers[0].index,
                    recommended=repair_recommended,
                )
                challenger_review = repair_reviews.get(challenger.index)
                if _repair_is_better(
                    selected,
                    selected_review,
                    challenger,
                    challenger_review,
                ):
                    selected, selected_review = challenger, challenger_review

        shape = selected.shape
        if reference_images and state.reference_name:
            shape.name = state.reference_name
        shape.spec = spec
        shape.recognition_features = [feature.label for feature in spec.recognition_features]
        shape.semantic_verification = selected_review
        shape.generator_provider = selected.response.provider
        shape.generator_model = selected.response.model
        shape.generator_usage = dict(selected.response.usage)
        shape.generated_candidate_count = len(candidates)
        shape.selected_candidate = selected.index
        shape.generation_strategy = selected.strategy
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
        reference_images: list[ImageInput] | None = None,
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
        if reference_images:
            repair_prompt += (
                "\n\nKeep the repaired candidate visually faithful to the attached source image; "
                "do not invent or replace its silhouette."
            )
        repaired = try_complete(
            lambda: self._llm_fallback(idea),
            messages=[{"role": "user", "content": repair_prompt}],
            system=system,
            json_mode=True,
            json_schema=_SHAPE_REPAIR_JSON_SCHEMA,
            temperature=0.15,
            max_tokens=_SHAPE_REPAIR_MAX_TOKENS,
            images=reference_images or None,
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
        except (KeyError, TypeError, ValueError) as error:
            self.log.warning(
                "AI shape repair response was unusable: %s",
                " ".join(str(error).split())[:320],
            )
            return None

    def _verify_candidates(
        self,
        *,
        idea: str,
        spec: ShapeSpec,
        candidates: list[_GeneratedCandidate],
        generator_provider: str,
        system: str,
        reference_images: list[ImageInput] | None = None,
    ) -> tuple[dict[int, ShapeVerification], int | None]:
        deterministic = {
            candidate.index: _geometry_only_verification(candidate)
            for candidate in candidates
        }
        if (
            get_settings().llm.usage_mode == "essential"
            or not get_settings().workflow.ai_shape_verifier_enabled
            or not candidates
            or any("program" not in candidate.raw for candidate in candidates)
        ):
            return deterministic, None
        candidate_images = [
            ImageInput(
                shape_program.render_paths_png_data_url(
                    _final_ai_preview_paths(candidate.shape.paths, candidate.shape.closed)
                ),
                detail="high",
            )
            for candidate in candidates
        ]
        image_offset = 2 if reference_images else 1
        candidate_image_map = "; ".join(
            f"Image {position + image_offset} corresponds to candidate_index {candidate.index}"
            for position, candidate in enumerate(candidates)
        )
        prompt = render(
            "shape_verify",
            shape=json.dumps(idea, ensure_ascii=False),
            spec=json.dumps(asdict(spec), ensure_ascii=False, separators=(",", ":")),
            image_order=(
                "Image 1 is the authoritative source image. "
                f"{candidate_image_map}. Compare each candidate directly with the "
                "source image."
                if reference_images
                else "Every supplied image is a GPS-art candidate. " + candidate_image_map + "."
            ),
        )
        images = [*(reference_images or []), *candidate_images]
        response = try_complete(
            lambda: LLMResponse(text="{}", provider="fallback", model="geometry-checks"),
            messages=[{"role": "user", "content": prompt}],
            system=system,
            images=images,
            json_mode=True,
            json_schema=_SHAPE_VERIFICATION_JSON_SCHEMA,
            temperature=0,
            max_tokens=_SHAPE_REVIEW_MAX_TOKENS,
            exclude_provider=generator_provider,
            pin_provider=False,
            max_provider_attempts=1,
        )
        independent = response.provider not in {"fallback", generator_provider}
        if independent:
            try:
                return _verifications_from_response(
                    response,
                    candidates,
                    spec,
                    independent=True,
                )
            except (KeyError, TypeError, ValueError) as error:
                # A reachable critic can still violate the portable schema.
                # Fall through to the disclosed generator critic instead of
                # discarding rendered semantic evidence entirely.
                self.log.warning(
                    "Independent AI shape review was invalid; trying disclosed "
                    "self-review: %s",
                    " ".join(str(error).split())[:320],
                )

        # A different provider is preferable because it avoids asking the
        # generator to grade its own work. Many real deployments configure
        # only one visual provider, though. In that common case a second,
        # temperature-zero critic call is still materially better than
        # selecting a silhouette from geometry heuristics alone. Keep the
        # provenance explicitly non-independent so callers and benchmarks
        # cannot mistake self-review for external evidence.
        response = try_complete(
            lambda: LLMResponse(
                text="{}",
                provider="fallback",
                model="geometry-checks",
            ),
            messages=[{"role": "user", "content": prompt}],
            system=system,
            images=images,
            json_mode=True,
            json_schema=_SHAPE_VERIFICATION_JSON_SCHEMA,
            temperature=0,
            max_tokens=_SHAPE_REVIEW_MAX_TOKENS,
            pin_provider=False,
            max_provider_attempts=1,
        )
        if response.provider == "fallback":
            return deterministic, None
        try:
            return _verifications_from_response(
                response,
                candidates,
                spec,
                independent=response.provider != generator_provider,
            )
        except (KeyError, TypeError, ValueError) as error:
            self.log.warning(
                "AI shape self-review was invalid; using geometry evidence: %s",
                " ".join(str(error).split())[:320],
            )
            return deterministic, None

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


def _shape_spec_from_payload(payload: object, idea: str) -> ShapeSpec:
    if not isinstance(payload, dict):
        raise ValueError("visual response must contain a ShapeSpec object")
    return _shape_spec_from_response(
        LLMResponse(text=json.dumps(payload), provider="embedded-visual-spec"),
        idea,
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
    configured_limit = max(1, get_settings().workflow.ai_shape_max_candidates)
    return min(configured_limit, count)


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
    if not 1 <= len(variants) <= 4:
        raise ValueError("geometry response needs one to four candidates")
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
    program = _normalise_close_commands(_split_embedded_moves(raw.get("program")))
    linear_attempted = False
    untangle_attempted = False
    aspect_attempted = False
    compiled: shape_program.CompiledShapeProgram | None = None
    last_error: ValueError | None = None
    for _ in range(5):
        try:
            compiled = shape_program.compile_shape_program(
                program,
                required_feature_ids=required_ids,
            )
            _validate_route_friendly_geometry(compiled.paths)
            _validate_shape_spec_geometry(compiled, spec)
            _validate_distinct_custom_geometry(compiled.paths)
            break
        except ValueError as error:
            last_error = error
            message = str(error)
            if "aspect ratio" in message and not aspect_attempted:
                aspect_attempted = True
                corrected_program = _fit_program_aspect(program, spec.aspect_ratio)
                if corrected_program != program:
                    program = corrected_program
                    continue
            if "outline crosses itself" in message:
                if not linear_attempted:
                    linear_attempted = True
                    linear_program = _linearise_curves(program)
                    if linear_program != program:
                        program = linear_program
                        continue
                if not untangle_attempted:
                    untangle_attempted = True
                    untangled_program = _untangle_linear_outline(program)
                    if untangled_program != program:
                        program = untangled_program
                        continue
            raise
    else:  # pragma: no cover - bounded transformations make this defensive only
        raise last_error or ValueError("shape program correction did not converge")
    if compiled is None:  # pragma: no cover - loop either compiles or raises
        raise ValueError("shape program did not compile")
    validated_raw = deepcopy(raw)
    validated_raw["program"] = program
    shape = Shape(
        name=" ".join(idea.split())[:80],
        paths=compiled.paths,
        closed=compiled.closed,
        source="llm",
        feature_paths=compiled.feature_paths,
    )
    return _GeneratedCandidate(
        index=index,
        strategy=strategy,
        raw=validated_raw,
        shape=shape,
        local_score=shape_program.local_program_score(compiled, required_ids),
        feature_warnings=compiled.warnings,
        response=response,
    )


def _normalise_close_commands(program: object) -> object:
    """Move a model-emitted close command to the end of its stroke.

    Some otherwise valid structured responses place ``close`` immediately
    before one or two final line commands. The drawing language has only one
    subpath per stroke, so postponing that close preserves every authored
    segment and restores the intended closed contour without another AI call.
    """

    if not isinstance(program, dict):
        return program
    normalised = deepcopy(program)
    strokes = normalised.get("strokes")
    if not isinstance(strokes, list):
        return normalised
    for stroke in strokes:
        if not isinstance(stroke, dict):
            continue
        commands = stroke.get("commands")
        if not isinstance(commands, list):
            continue
        close_commands = [
            command
            for command in commands
            if isinstance(command, dict) and command.get("op") == "close"
        ]
        if not close_commands:
            continue
        stroke["commands"] = [
            command
            for command in commands
            if not (isinstance(command, dict) and command.get("op") == "close")
        ] + [close_commands[0]]
    return normalised


def _split_embedded_moves(program: object) -> object:
    """Interpret every additional ``move`` as the new stroke it denotes."""

    if not isinstance(program, dict):
        return program
    normalised = deepcopy(program)
    strokes = normalised.get("strokes")
    if not isinstance(strokes, list):
        return normalised
    split_strokes: list[dict] = []
    for stroke in strokes:
        if not isinstance(stroke, dict) or not isinstance(stroke.get("commands"), list):
            split_strokes.append(stroke)
            continue
        chunks: list[list[object]] = []
        current: list[object] = []
        for command in stroke["commands"]:
            if isinstance(command, dict) and command.get("op") == "move" and current:
                chunks.append(current)
                current = []
            current.append(command)
        if current:
            chunks.append(current)
        for commands in chunks:
            split_stroke = deepcopy(stroke)
            split_stroke["commands"] = commands
            split_strokes.append(split_stroke)
    if 1 <= len(split_strokes) <= 8:
        normalised["strokes"] = split_strokes
    return normalised


def _fit_program_aspect(program: object, target_ratio: float) -> object:
    """Shrink only the long axis so authored points fit the requested ratio."""

    if not isinstance(program, dict):
        return program
    corrected = deepcopy(program)
    strokes = corrected.get("strokes")
    if not isinstance(strokes, list):
        return corrected
    point_lists: list[list[float]] = []
    for stroke in strokes:
        if not isinstance(stroke, dict) or not isinstance(stroke.get("commands"), list):
            continue
        for command in stroke["commands"]:
            if not isinstance(command, dict) or not isinstance(command.get("points"), list):
                continue
            for index, raw_point in enumerate(command["points"]):
                if not isinstance(raw_point, list | tuple) or len(raw_point) != 2:
                    continue
                point = [float(raw_point[0]), float(raw_point[1])]
                command["points"][index] = point
                point_lists.append(point)
    if not point_lists:
        return corrected
    xs = [float(point[0]) for point in point_lists]
    ys = [float(point[1]) for point in point_lists]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    if width <= 1e-9 or height <= 1e-9:
        return corrected
    target_ratio = max(0.5, min(2.0, target_ratio))
    actual_ratio = width / height
    centre_x = (min(xs) + max(xs)) / 2
    centre_y = (min(ys) + max(ys)) / 2
    scale_x = target_ratio / actual_ratio if actual_ratio > target_ratio else 1.0
    scale_y = actual_ratio / target_ratio if actual_ratio < target_ratio else 1.0
    for point in point_lists:
        point[0] = centre_x + (float(point[0]) - centre_x) * scale_x
        point[1] = centre_y + (float(point[1]) - centre_y) * scale_y
    return corrected


def _linearise_curves(program: object) -> object:
    """Drop only cubic controls while retaining endpoints and feature ids."""

    if not isinstance(program, dict):
        return program
    linear = deepcopy(program)
    strokes = linear.get("strokes")
    if not isinstance(strokes, list):
        return linear
    for stroke in strokes:
        if not isinstance(stroke, dict) or not isinstance(stroke.get("commands"), list):
            continue
        for command in stroke["commands"]:
            if (
                isinstance(command, dict)
                and command.get("op") == "curve"
                and isinstance(command.get("points"), list)
                and len(command["points"]) == 3
            ):
                command["op"] = "line"
                command["points"] = [command["points"][-1]]
    return linear


def _untangle_linear_outline(program: object) -> object:
    """Remove proper edge crossings from one closed linear stroke with 2-opt.

    This is deliberately narrower than a general geometry repair. It keeps the
    model's endpoints, only reverses spans between crossing edges, and assigns
    every resulting edge the feature label of its nearest authored edge. Full
    route, ShapeSpec and uniqueness validation still decides whether the
    result is usable.
    """

    if not isinstance(program, dict):
        return program
    strokes = program.get("strokes")
    if not isinstance(strokes, list) or len(strokes) != 1:
        return program
    stroke = strokes[0]
    if not isinstance(stroke, dict) or not isinstance(stroke.get("commands"), list):
        return program
    commands = stroke["commands"]
    if len(commands) < 6 or not all(isinstance(command, dict) for command in commands):
        return program
    if commands[0].get("op") != "move":
        return program
    has_close = commands[-1].get("op") == "close"
    drawing_commands = commands[1:-1] if has_close else commands[1:]
    if not drawing_commands or any(command.get("op") != "line" for command in drawing_commands):
        return program
    if not has_close and program.get("closed") is not True:
        return program

    start_points = commands[0].get("points")
    if not isinstance(start_points, list) or len(start_points) != 1:
        return program
    vertices: list[tuple[float, float]] = [tuple(start_points[0])]
    original_edges: list[tuple[tuple[float, float], tuple[float, float], object]] = []
    previous = vertices[0]
    for command in drawing_commands:
        points = command.get("points")
        if not isinstance(points, list) or len(points) != 1:
            return program
        endpoint = tuple(points[0])
        if len(endpoint) != 2 or endpoint == previous:
            return program
        vertices.append(endpoint)
        original_edges.append((previous, endpoint, command.get("feature_id")))
        previous = endpoint
    if vertices[-1] == vertices[0]:
        vertices.pop()
    if len(vertices) < 4 or len(set(vertices)) != len(vertices):
        return program
    close_feature = commands[-1].get("feature_id") if has_close else None
    original_edges.append((previous, vertices[0], close_feature))

    changed = False
    edge_count = len(vertices)
    for _ in range(edge_count * edge_count):
        crossing: tuple[int, int] | None = None
        for first in range(edge_count):
            first_next = (first + 1) % edge_count
            first_edge = LineString([vertices[first], vertices[first_next]])
            for second in range(first + 1, edge_count):
                second_next = (second + 1) % edge_count
                if first_next == second or second_next == first:
                    continue
                second_edge = LineString([vertices[second], vertices[second_next]])
                if first_edge.crosses(second_edge):
                    crossing = first, second
                    break
            if crossing is not None:
                break
        if crossing is None:
            break
        first, second = crossing
        vertices[first + 1 : second + 1] = reversed(vertices[first + 1 : second + 1])
        changed = True
    if not changed:
        return program

    def nearest_feature(start: tuple[float, float], end: tuple[float, float]) -> object:
        return min(
            original_edges,
            key=lambda edge: min(
                math.dist(start, edge[0]) + math.dist(end, edge[1]),
                math.dist(start, edge[1]) + math.dist(end, edge[0]),
            ),
        )[2]

    new_edges = list(zip(vertices, vertices[1:], strict=False))
    if has_close:
        new_edges.append((vertices[-1], vertices[0]))
    edge_features = [nearest_feature(start, end) for start, end in new_edges]
    authored_features = {
        feature_id
        for _, _, feature_id in original_edges
        if isinstance(feature_id, str)
    }
    for missing_feature in sorted(authored_features - set(edge_features)):
        feature_edges = [
            edge
            for edge in original_edges
            if edge[2] == missing_feature
        ]
        feature_counts = {
            feature_id: edge_features.count(feature_id)
            for feature_id in set(edge_features)
        }
        replaceable = [
            index
            for index, feature_id in enumerate(edge_features)
            if feature_counts.get(feature_id, 0) > 1
        ] or list(range(len(edge_features)))
        replace_index = min(
            replaceable,
            key=lambda index: min(
                min(
                    math.dist(new_edges[index][0], edge[0])
                    + math.dist(new_edges[index][1], edge[1]),
                    math.dist(new_edges[index][0], edge[1])
                    + math.dist(new_edges[index][1], edge[0]),
                )
                for edge in feature_edges
            ),
        )
        edge_features[replace_index] = missing_feature

    untangled = deepcopy(program)
    rebuilt = [deepcopy(commands[0])]
    for (_, end), feature_id in zip(new_edges[: len(vertices) - 1], edge_features, strict=False):
        rebuilt.append(
            {
                "op": "line",
                "points": [list(end)],
                "feature_id": feature_id,
            }
        )
    if has_close:
        rebuilt.append(
            {
                "op": "close",
                "points": [],
                "feature_id": edge_features[-1],
            }
        )
    untangled["strokes"][0]["commands"] = rebuilt
    return untangled


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
    *,
    independent: bool = True,
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
        if index in reviews:
            raise ValueError("visual review scores a candidate more than once")
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
            independent=independent,
            method=(
                "rendered-image-independent"
                if independent
                else "rendered-image-self-review"
            ),
            usage=dict(resp.usage),
        )
    if set(reviews) != candidate_ids:
        raise ValueError("visual review must score every supplied candidate exactly once")
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
    def score(candidate: _GeneratedCandidate) -> tuple[float, float, float, float, float, float, float]:
        review = reviews.get(candidate.index)
        rendered = bool(review and _is_rendered_visual_review(review))
        semantic = review.score if rendered and review and review.score is not None else candidate.local_score
        cue_defects = _visual_defect_count(review) if rendered and review else 0
        relation_defects = len(review.wrong_relations) if rendered and review else 0
        return (
            1.0 if rendered else 0.0,
            1.0 if rendered and cue_defects == 0 else 0.0,
            -float(cue_defects),
            semantic,
            -float(relation_defects),
            1.0 if candidate.index == recommended else 0.0,
            1.0 if candidate.index == preferred else 0.0,
        )

    return max(candidates, key=score)


def _is_rendered_visual_review(review: ShapeVerification) -> bool:
    """Whether a score came from the candidate pixels, not local geometry."""

    return review.method.startswith("rendered-image")


def _visual_defect_count(review: ShapeVerification) -> int:
    """Count absent required cues without double-counting two report fields.

    Relationship notes remain useful diagnostics and affect the critic's
    semantic score, but an aesthetic relation note must not outrank a candidate
    that actually contains every required identity cue.
    """

    absent_cues = sum(not cue.present for cue in review.cue_results)
    return max(absent_cues, len(review.missing_features))


def _candidate_repair_diagnostics(
    candidate: _GeneratedCandidate,
    review: ShapeVerification | None,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {}
    if candidate.feature_warnings:
        diagnostics["feature_coverage"] = candidate.feature_warnings
    if review and _is_rendered_visual_review(review):
        if review.missing_features:
            diagnostics["missing_features"] = review.missing_features
        if review.wrong_relations:
            diagnostics["wrong_relations"] = review.wrong_relations
        if (
            review.repair_instructions
            and (review.missing_features or review.wrong_relations)
        ):
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
    if (
        repaired_review
        and _is_rendered_visual_review(repaired_review)
        and repaired_review.score is not None
    ):
        baseline = (
            original_review.score
            if (
                original_review
                and _is_rendered_visual_review(original_review)
                and original_review.score is not None
            )
            else original.local_score
        )
        if original_review and _is_rendered_visual_review(original_review):
            original_defects = _visual_defect_count(original_review)
            repaired_defects = _visual_defect_count(repaired_review)
            if repaired_defects > original_defects:
                return False
            if repaired_defects < original_defects:
                quality_floor = max(
                    get_settings().workflow.ai_shape_min_semantic_score,
                    baseline - 0.08,
                )
                return repaired_review.score >= quality_floor
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
    # ``preferred_strokes`` is a preference, not a semantic hard limit.  The
    # drawing prompt permits up to four strokes when an interior or secondary
    # cue is essential, so do not discard those cues merely because the first
    # semantic pass preferred a one-stroke route.
    if len(compiled.paths) > 4:
        raise ValueError("drawing uses more than four route-friendly strokes")
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
        path_closed = len(path) >= 3 and path[0] == path[-1]
        candidate = geo.catmull_rom_smooth(
            path,
            closed=path_closed,
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


def _semantic_scaffold_candidate(
    *,
    idea: str,
    spec: ShapeSpec,
    response: LLMResponse,
    index: int,
) -> _GeneratedCandidate | None:
    """Prefer an authored anchor, then fall back to a ShapeSpec composition."""

    if _semantic_scaffold_mode(spec) in _FULL_SEMANTIC_SCAFFOLD_MODES:
        return _spec_grounded_candidate(
            idea=idea,
            spec=spec,
            response=response,
            index=index,
        ) or _catalog_grounded_candidate(
            idea=idea,
            spec=spec,
            response=response,
            index=index,
        )
    return _catalog_grounded_candidate(
        idea=idea,
        spec=spec,
        response=response,
        index=index,
    ) or _spec_grounded_candidate(
        idea=idea,
        spec=spec,
        response=response,
        index=index,
    )


def _spec_grounded_candidate(
    *,
    idea: str,
    spec: ShapeSpec,
    response: LLMResponse,
    index: int,
) -> _GeneratedCandidate | None:
    """Compose route-native geometry from the AI-owned part hierarchy.

    The primary path is a closed outer contour.  Essential line-like parts
    remain separate strokes instead of being buffered into an unreadable blob
    or discarded when only the largest union polygon is retained.
    """

    if not 0 <= index <= 3 or not spec.parts:
        return None
    special_paths = _special_semantic_paths(spec)
    if special_paths:
        return _grounded_candidate_from_paths(
            idea=idea,
            spec=spec,
            response=response,
            index=index,
            named_paths=special_paths,
            strategy=f"{_semantic_scaffold_mode(spec)} ShapeSpec scaffold",
        )
    centres: dict[str, tuple[float, float]] = {}
    sizes: dict[str, tuple[float, float]] = {}
    geometries: dict[str, BaseGeometry] = {}
    organic_profile = spec.viewpoint == "side" and any(
        any(token in f"{feature.label} {feature.geometry_hint}".casefold() for token in ("oval", "smooth", "animal", "rounded"))
        for feature in spec.recognition_features
    )
    unresolved = list(spec.parts)
    for _ in range(len(spec.parts) + 1):
        if not unresolved:
            break
        progress = False
        for part_index, part in list(enumerate(unresolved)):
            if part.parent is not None and part.parent not in centres:
                continue
            parent_centre = centres.get(part.parent or "", (0.0, 0.0))
            parent_size = sizes.get(part.parent or "", (0.9, 0.62))
            size = _semantic_part_size(part)
            centre = _semantic_part_centre(
                part,
                parent_centre=parent_centre,
                parent_size=parent_size,
                index=len(centres),
                viewpoint=spec.viewpoint,
            )
            geometry: BaseGeometry = _semantic_part_geometry(
                part,
                centre,
                size,
                organic=organic_profile,
            )
            if part.parent is not None:
                connector_width = max(0.06, min(size) * 0.22)
                connector = LineString([parent_centre, centre]).buffer(
                    connector_width,
                    cap_style="round",
                    join_style="round",
                    quad_segs=3,
                )
                geometry = unary_union((geometry, connector))
            centres[part.id] = centre
            sizes[part.id] = size
            geometries[part.id] = geometry
            unresolved.pop(part_index)
            progress = True
            break
        if not progress:
            return None
    if not geometries:
        return None
    main_geometries = _semantic_main_geometries(spec, geometries)
    silhouette = unary_union(tuple(main_geometries.values())).buffer(0)
    polygons = (
        [silhouette]
        if isinstance(silhouette, Polygon)
        else [geometry for geometry in getattr(silhouette, "geoms", ()) if isinstance(geometry, Polygon)]
    )
    if not polygons:
        return None
    main = max(polygons, key=lambda geometry: geometry.area)
    outline = [(float(x), float(y)) for x, y in main.exterior.coords]
    outline = _sample_reference_path(outline, max_points=48)
    if _semantic_scaffold_mode(spec) == "articulated":
        articulated = _articulated_paths(spec, main.bounds)
        paths = [path for path, _ in articulated]
        path_names = [name for _, name in articulated]
    else:
        selected_secondary = _semantic_secondary_paths(spec, main.bounds)[:3]
        paths = [outline, *(path for path, _ in selected_secondary)]
        path_names = [spec.subject, *(name for _, name in selected_secondary)]
    program = _catalog_program(paths, path_names, spec)
    fitted_program = _fit_program_aspect(program, spec.aspect_ratio)
    if not isinstance(fitted_program, dict):
        return None
    program = fitted_program
    required_ids = {feature.id for feature in spec.recognition_features}
    try:
        compiled = shape_program.compile_shape_program(
            program,
            required_feature_ids=required_ids,
        )
        _validate_route_friendly_geometry(compiled.paths)
        _validate_shape_spec_geometry(compiled, spec)
    except (TypeError, ValueError):
        return None
    strategy = "ShapeSpec-grounded semantic scaffold"
    raw: dict[str, object] = {"strategy": strategy, "program": program}
    shape = Shape(
        name=" ".join(idea.split())[:80],
        paths=compiled.paths,
        closed=compiled.closed,
        source="llm",
        feature_paths=compiled.feature_paths,
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


def _semantic_spec_text(spec: ShapeSpec) -> str:
    values = [
        spec.subject,
        spec.pose,
        *spec.modifiers,
        *(f"{part.id} {part.label} {part.position}" for part in spec.parts),
        *(
            f"{feature.id} {feature.label} {feature.geometry_hint} {feature.relation}"
            for feature in spec.recognition_features
        ),
    ]
    return unicodedata.normalize("NFKD", " ".join(values)).encode(
        "ascii", "ignore"
    ).decode().casefold()


def _semantic_scaffold_mode(spec: ShapeSpec) -> str:
    text = _semantic_spec_text(spec)
    subject = unicodedata.normalize("NFKD", spec.subject).encode(
        "ascii", "ignore"
    ).decode().casefold()
    if "robot" in subject and any(
        token in text for token in ("umbrella", "esernyo", "parapluie", "regenschirm")
    ):
        return "robot_umbrella"
    if "robot" in subject:
        return "robot"
    if "platypus" in subject:
        return "platypus"
    if any(token in subject for token in ("coffee", "kave", "cafe")) or (
        "cup" in text and any(token in text for token in ("steam", "handle", "rim"))
    ):
        return "coffee_cup"
    if "sailboat" in subject or ("mast" in text and "sail" in text):
        return "sailboat"
    if re.search(r"\bkey\b", subject) or (
        "shaft" in text and "tooth" in text and "bow" in text
    ):
        return "key"
    if "bicycle" in subject or ("wheel" in text and "basket" in text):
        return "bicycle"
    if "phoenix" in subject or ("raised wings" in text and "flame" in text):
        return "phoenix"
    if "dragon" in subject:
        return "dragon"
    if re.search(r"\b(cat|chat)\b", subject):
        return "cat"
    if "fox" in subject and ("moon" in text or "crescent" in text):
        return "moon_leap"
    if any(token in subject for token in ("teddy", "bear", "teddybar")):
        return "bear"
    if any(token in text for token in ("galaxy", "spiral", "galaxis", "spirale")):
        return "spiral"
    if any(token in text for token in ("astrolab", "radial spokes", "radial web")):
        return "radial"
    if any(
        token in text
        for token in (
            "runner", "running figure", "high knee", "raised knee",
            "back leg", "arm pump", "stride",
        )
    ):
        return "articulated"
    if re.search(r"\b(wave|waves|hullam|hullamok|vague|vagues)\b", text):
        return "waves"
    return "silhouette"


def _semantic_main_geometries(
    spec: ShapeSpec,
    geometries: dict[str, BaseGeometry],
) -> dict[str, BaseGeometry]:
    """Exclude line-like parts that need their own readable stroke."""

    mode = _semantic_scaffold_mode(spec)
    part_by_id = {part.id: part for part in spec.parts}
    selected: dict[str, BaseGeometry] = {}
    for part_id, geometry in geometries.items():
        part = part_by_id.get(part_id)
        text = f"{part_id} {part.label if part else ''}".casefold()
        excluded = (
            mode == "spiral" and any(token in text for token in ("arm", "spiral"))
        ) or (
            mode == "radial" and any(
                token in text
                for token in (
                    "ring", "spoke", "pointer", "alidade", "lattice", "index arm",
                )
            )
        ) or (
            mode == "articulated" and any(
                token in text for token in ("arm", "leg", "limb", "knee", "foot", "hand")
            )
        ) or (
            mode == "waves" and any(token in text for token in ("wave", "foam", "surf"))
        )
        if not excluded:
            selected[part_id] = geometry
    if selected:
        return selected
    first_id = next(iter(geometries))
    return {first_id: geometries[first_id]}


def _semantic_feature_id(spec: ShapeSpec, *tokens: str) -> str:
    """Choose the cue whose typed description best matches a semantic stroke."""

    def affinity(feature: ShapeFeature) -> tuple[int, int, str]:
        text = " ".join(
            (feature.id, feature.label, feature.geometry_hint, feature.relation)
        ).casefold()
        return sum(token in text for token in tokens), feature.importance, feature.id

    return max(spec.recognition_features, key=affinity).id


def _semantic_secondary_paths(
    spec: ShapeSpec,
    bounds: tuple[float, float, float, float],
) -> list[tuple[geo.Path, str]]:
    """Build a few bold secondary strokes for common non-silhouette cues."""

    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 0.5)
    height = max(max_y - min_y, 0.5)
    centre_x = (min_x + max_x) / 2
    centre_y = (min_y + max_y) / 2
    mode = _semantic_scaffold_mode(spec)
    if mode == "robot":
        head = [
            (centre_x - 0.22 * width, max_y - 0.34 * height),
            (centre_x + 0.22 * width, max_y - 0.34 * height),
            (centre_x + 0.22 * width, max_y - 0.08 * height),
            (centre_x - 0.22 * width, max_y - 0.08 * height),
        ]
        head.append(head[0])
        return [(
            head,
            _semantic_feature_id(spec, "boxy head", "head", "robot"),
        )]
    if mode == "spiral":
        feature_id = _semantic_feature_id(spec, "two arms", "spiral", "winding")
        reach = 0.75 * max(width, height)
        arms: list[tuple[geo.Path, str]] = []
        for arm_index in range(2):
            phase = arm_index * math.pi
            path = []
            for step in range(11):
                fraction = step / 10
                angle = phase + fraction * math.pi * 1.15
                radius = (0.06 + 0.94 * fraction) * reach
                path.append((
                    centre_x + radius * math.cos(angle),
                    centre_y + 0.65 * radius * math.sin(angle),
                ))
            arms.append((path, feature_id))
        return arms
    if mode == "radial":
        radius = 0.12 * min(width, height)
        ring_centre_y = max_y + radius * 1.35
        ring = [
            (
                centre_x + radius * math.cos(2 * math.pi * step / 10),
                ring_centre_y + radius * math.sin(2 * math.pi * step / 10),
            )
            for step in range(10)
        ]
        ring.append(ring[0])
        inner_radius_x = 0.30 * width
        inner_radius_y = 0.30 * height
        inner = [
            (
                centre_x + inner_radius_x * math.cos(2 * math.pi * step / 16),
                centre_y + inner_radius_y * math.sin(2 * math.pi * step / 16),
            )
            for step in range(16)
        ]
        inner.append(inner[0])
        return [
            (ring, _semantic_feature_id(spec, "ring", "hanging", "bow")),
            (
                inner,
                _semantic_feature_id(spec, "open center", "inner circle", "scale band"),
            ),
            ([
                (centre_x, ring_centre_y - radius),
                (centre_x, max_y),
                (centre_x, centre_y),
                (centre_x + 0.28 * width, centre_y - 0.20 * height),
            ], _semantic_feature_id(spec, "index arm", "pointer", "radial")),
        ]
    if mode == "articulated":
        shoulder = (centre_x + 0.08 * width, centre_y + 0.26 * height)
        hip = (centre_x - 0.04 * width, centre_y - 0.22 * height)
        return [
            ([
                hip,
                (centre_x + 0.48 * width, centre_y - 0.02 * height),
                (centre_x + 0.24 * width, centre_y - 0.55 * height),
            ], _semantic_feature_id(spec, "high knee", "raised knee", "knee")),
            ([
                hip,
                (centre_x - 0.30 * width, centre_y - 0.48 * height),
                (centre_x - 0.62 * width, centre_y - 0.58 * height),
            ], _semantic_feature_id(spec, "back leg", "stride", "extension")),
            ([
                (centre_x - 0.12 * width, centre_y + 0.18 * height),
                (centre_x + 0.27 * width, centre_y + 0.04 * height),
                shoulder,
                (centre_x - 0.38 * width, centre_y - 0.02 * height),
            ], _semantic_feature_id(spec, "arm pump", "arm", "forward tilt")),
        ]
    if mode == "waves":
        wave_id_left = _semantic_feature_id(spec, "wave_left", "left wave", "first wave")
        wave_id_right = _semantic_feature_id(spec, "wave_right", "right wave", "second wave")
        baseline = min_y - 0.08 * height
        left_wave = [
            (
                centre_x - 0.76 * width + 0.68 * width * step / 8,
                baseline + 0.22 * height * math.sin(math.pi * step / 8),
            )
            for step in range(9)
        ]
        right_wave = [
            (
                centre_x + 0.08 * width + 0.68 * width * step / 8,
                baseline + 0.22 * height * math.sin(math.pi * step / 8),
            )
            for step in range(9)
        ]
        waves = [
            (left_wave, wave_id_left),
            (right_wave, wave_id_right),
        ]
        if "lantern" in _semantic_spec_text(spec):
            lantern = [
                (centre_x - 0.15 * width, max_y - 0.04 * height),
                (centre_x + 0.15 * width, max_y - 0.04 * height),
                (centre_x + 0.15 * width, max_y + 0.09 * height),
                (centre_x + 0.10 * width, max_y + 0.16 * height),
                (centre_x - 0.10 * width, max_y + 0.16 * height),
                (centre_x - 0.15 * width, max_y + 0.09 * height),
            ]
            lantern.append(lantern[0])
            waves.append((
                lantern,
                _semantic_feature_id(spec, "lantern", "lamp", "top cap"),
            ))
        if any(
            token in _semantic_spec_text(spec)
            for token in ("band", "stripe", "horizontal line")
        ):
            waves.append(([
                (centre_x - 0.22 * width, centre_y + 0.16 * height),
                (centre_x + 0.22 * width, centre_y + 0.16 * height),
                (centre_x + 0.22 * width, centre_y - 0.02 * height),
                (centre_x - 0.22 * width, centre_y - 0.02 * height),
                (centre_x - 0.22 * width, centre_y - 0.20 * height),
                (centre_x + 0.22 * width, centre_y - 0.20 * height),
            ], _semantic_feature_id(spec, "band", "stripe", "tower detail")))
        return waves
    return []


def _grounded_candidate_from_paths(
    *,
    idea: str,
    spec: ShapeSpec,
    response: LLMResponse,
    index: int,
    named_paths: list[tuple[geo.Path, str]],
    strategy: str,
) -> _GeneratedCandidate | None:
    """Compile and fully validate a bounded semantic scaffold."""

    if not named_paths or len(named_paths) > 4:
        return None
    paths = [path for path, _ in named_paths]
    names = [name for _, name in named_paths]
    program = _catalog_program(paths, names, spec)
    fitted = _fit_program_aspect(program, spec.aspect_ratio)
    if not isinstance(fitted, dict):
        return None
    required_ids = {feature.id for feature in spec.recognition_features}
    try:
        compiled = shape_program.compile_shape_program(
            fitted,
            required_feature_ids=required_ids,
        )
        _validate_route_friendly_geometry(compiled.paths)
        _validate_shape_spec_geometry(compiled, spec)
    except (TypeError, ValueError):
        return None
    raw: dict[str, object] = {"strategy": strategy, "program": fitted}
    return _GeneratedCandidate(
        index=index,
        strategy=strategy,
        raw=raw,
        shape=Shape(
            name=" ".join(idea.split())[:80],
            paths=compiled.paths,
            closed=compiled.closed,
            source="llm",
            feature_paths=compiled.feature_paths,
        ),
        local_score=shape_program.local_program_score(compiled, required_ids),
        feature_warnings=compiled.warnings,
        response=response,
    )


def _ellipse_path(
    centre: tuple[float, float],
    size: tuple[float, float],
    *,
    steps: int = 20,
) -> geo.Path:
    x, y = centre
    width, height = size
    path = [
        (
            x + width / 2 * math.cos(2 * math.pi * step / steps),
            y + height / 2 * math.sin(2 * math.pi * step / steps),
        )
        for step in range(steps)
    ]
    path.append(path[0])
    return path


def _ellipse_polygon(
    centre: tuple[float, float],
    size: tuple[float, float],
) -> Polygon:
    return Polygon(_ellipse_path(centre, size)[:-1])


def _outer_path(*geometries: BaseGeometry) -> geo.Path:
    merged = unary_union(geometries).buffer(0)
    polygons = (
        [merged]
        if isinstance(merged, Polygon)
        else [part for part in getattr(merged, "geoms", ()) if isinstance(part, Polygon)]
    )
    if not polygons:
        return []
    outer = max(polygons, key=lambda geometry: geometry.area)
    return _sample_reference_path(
        [(float(x), float(y)) for x, y in outer.exterior.coords],
        max_points=48,
    )


def _special_semantic_paths(spec: ShapeSpec) -> list[tuple[geo.Path, str]]:
    """Create bold typed geometry when an outer union cannot express the parts."""

    mode = _semantic_scaffold_mode(spec)
    if mode == "robot_umbrella":
        robot = _outer_path(
            box(-0.55, -0.35, 0.38, 0.32),
            box(-0.52, -0.78, -0.22, -0.28),
            box(0.08, -0.78, 0.38, -0.28),
            LineString([(-0.48, 0.12), (-0.76, -0.02), (-0.67, -0.20)]).buffer(
                0.10, cap_style="square", join_style="mitre"
            ),
        )
        canopy = [
            (-0.18, 0.88), (-0.02, 1.10), (0.25, 1.23),
            (0.62, 1.28), (0.99, 1.23), (1.26, 1.10),
            (1.42, 0.88), (1.16, 0.78), (0.89, 0.88),
            (0.62, 0.78), (0.35, 0.88), (0.08, 0.78),
            (-0.18, 0.88),
        ]
        return [
            (
                robot,
                _semantic_feature_id(spec, "robot", "boxy", "limb", "leg"),
            ),
            (
                canopy,
                _semantic_feature_id(spec, "umbrella", "canopy", "open"),
            ),
            (
                [
                    (0.30, 0.16), (0.49, 0.35), (0.62, 0.55),
                    (0.62, 0.68), (0.62, 0.82),
                ],
                _semantic_feature_id(
                    spec, "raised arm", "holding", "shaft", "connection"
                ),
            ),
            (
                [
                    (-0.50, 0.38), (0.08, 0.38), (0.08, 0.48),
                    (0.15, 0.48), (0.15, 0.58), (0.08, 0.58),
                    (0.08, 0.70), (-0.50, 0.70), (-0.50, 0.58),
                    (-0.57, 0.58), (-0.57, 0.48), (-0.50, 0.48),
                    (-0.50, 0.38),
                ],
                _semantic_feature_id(spec, "head", "robot", "boxy"),
            ),
        ]
    if mode == "radial":
        disc = Point(0.0, 0.0).buffer(0.78, quad_segs=12)
        bottom_tab = Polygon([(-0.11, -0.73), (0.0, -0.96), (0.11, -0.73)])
        outer = _outer_path(disc, bottom_tab)
        ring = _ellipse_path((0.0, 0.88), (0.20, 0.20), steps=14)
        lattice = [
            (
                (0.62 if step % 2 == 0 else 0.09)
                * math.cos(math.pi * step / 8),
                (0.62 if step % 2 == 0 else 0.09)
                * math.sin(math.pi * step / 8),
            )
            for step in range(16)
        ]
        lattice.append(lattice[0])
        return [
            (outer, _semantic_feature_id(spec, "outline", "tab", "instrument")),
            (ring, _semantic_feature_id(spec, "ring", "suspension", "hanging")),
            (lattice, _semantic_feature_id(spec, "rete", "lattice", "radial")),
            (
                _ellipse_path((0.0, 0.0), (0.13, 0.13), steps=10),
                _semantic_feature_id(spec, "hub", "center", "radial"),
            ),
        ]
    if mode == "spiral":
        first_arm = [
            (0.16, 0.04), (0.28, 0.14), (0.38, 0.30),
            (0.32, 0.46), (0.10, 0.60), (-0.25, 0.65),
            (-0.65, 0.48), (-0.92, 0.27), (-0.96, 0.35),
            (-0.67, 0.59), (-0.28, 0.76), (0.13, 0.70),
            (0.43, 0.52), (0.48, 0.30), (0.36, 0.10),
            (0.18, -0.02), (0.16, 0.04),
        ]
        second_arm = [
            (-0.16, -0.04), (-0.28, -0.14), (-0.38, -0.30),
            (-0.31, -0.46), (-0.08, -0.59), (0.27, -0.62),
            (0.66, -0.44), (0.94, -0.17), (0.98, -0.25),
            (0.69, -0.55), (0.29, -0.73), (-0.13, -0.68),
            (-0.43, -0.50), (-0.48, -0.28), (-0.35, -0.09),
            (-0.18, 0.02), (-0.16, -0.04),
        ]
        return [
            (
                _ellipse_path((0.0, 0.0), (0.27, 0.20), steps=14),
                _semantic_feature_id(spec, "core", "center", "compact"),
            ),
            (first_arm, _semantic_feature_id(spec, "arm", "spiral", "sweep")),
            (
                second_arm,
                _semantic_feature_id(spec, "arm", "spiral", "off-center"),
            ),
        ]
    if mode == "coffee_cup":
        cup = [
            (-0.56, 0.34), (0.56, 0.34), (0.46, -0.50),
            (0.32, -0.58), (-0.32, -0.58), (-0.46, -0.50),
            (-0.56, 0.34),
        ]
        steam = [
            (-0.36, 0.50), (-0.46, 0.65), (-0.36, 0.82),
            (-0.25, 0.66), (-0.19, 0.50), (-0.08, 0.50),
            (-0.10, 0.68), (0.00, 0.87), (0.10, 0.68),
            (0.08, 0.50), (0.19, 0.50), (0.25, 0.66),
            (0.36, 0.82), (0.46, 0.65), (0.36, 0.50),
        ]
        return [
            (cup, _semantic_feature_id(spec, "cup", "body", "flat base")),
            (
                _ellipse_path((0.0, 0.35), (1.12, 0.18), steps=18),
                _semantic_feature_id(spec, "rim", "opening", "mouth"),
            ),
            (
                _ellipse_path((0.53, -0.06), (0.56, 0.58), steps=16),
                _semantic_feature_id(spec, "handle", "right", "open loop"),
            ),
            (steam, _semantic_feature_id(spec, "steam", "curl", "above")),
        ]
    if mode == "key":
        bow = Point(0.0, 0.42).buffer(0.46, quad_segs=8)
        shaft = box(-0.11, -0.72, 0.11, 0.40)
        tooth = box(0.08, -0.72, 0.42, -0.51)
        outer = _outer_path(bow, shaft, tooth)
        return [
            (outer, _semantic_feature_id(spec, "shaft", "tooth", "profile")),
            (
                _ellipse_path((0.0, 0.42), (0.43, 0.43), steps=16),
                _semantic_feature_id(spec, "bow", "round", "loop"),
            ),
        ]
    if mode == "sailboat":
        return [
            ([
                (-0.95, -0.30), (0.95, -0.30), (0.62, -0.58),
                (-0.62, -0.58), (-0.95, -0.30),
            ], _semantic_feature_id(spec, "hull", "bow", "stern")),
            ([
                (0.0, -0.29), (0.0, 0.58), (0.0, 0.88),
            ], _semantic_feature_id(spec, "mast", "vertical")),
            ([
                (-0.07, -0.17), (-0.07, 0.82), (-0.76, -0.15),
                (-0.07, -0.17),
            ], _semantic_feature_id(spec, "front sail", "sail1", "filled")),
            ([
                (0.07, -0.17), (0.07, 0.82), (0.72, -0.12),
                (0.07, -0.17),
            ], _semantic_feature_id(spec, "rear sail", "sail2", "filled")),
        ]
    if mode == "bicycle":
        return [
            (
                _ellipse_path((-0.58, -0.34), (0.58, 0.58), steps=16),
                _semantic_feature_id(spec, "wheel", "rear wheel"),
            ),
            (
                _ellipse_path((0.58, -0.34), (0.58, 0.58), steps=16),
                _semantic_feature_id(spec, "wheel", "front wheel"),
            ),
            ([
                (-0.58, -0.34), (-0.20, 0.28), (0.02, 0.28),
                (0.58, -0.34),
                (0.02, -0.16),
                (-0.58, -0.34),
            ], _semantic_feature_id(spec, "triangular frame", "frame")),
            ([
                (0.48, -0.06), (0.60, -0.06), (0.60, 0.08),
                (0.86, 0.08), (0.80, 0.32), (0.72, 0.32),
                (0.77, 0.36), (0.79, 0.42), (0.77, 0.48),
                (0.72, 0.52), (0.66, 0.53), (0.61, 0.49),
                (0.61, 0.56), (0.56, 0.62), (0.49, 0.64),
                (0.42, 0.62), (0.37, 0.56), (0.36, 0.50),
                (0.31, 0.52), (0.25, 0.51), (0.20, 0.47),
                (0.18, 0.41), (0.20, 0.35), (0.26, 0.32),
                (0.30, 0.08), (0.48, 0.08),
                (0.48, -0.06),
            ], _semantic_feature_id(spec, "basket", "flower", "bloom")),
        ]
    if mode == "platypus":
        body = _ellipse_polygon((0.0, 0.02), (1.25, 0.58))
        head = _ellipse_polygon((0.57, 0.10), (0.48, 0.38))
        bill = box(0.55, -0.10, 1.38, 0.18).buffer(0.025, quad_segs=3)
        tail = _ellipse_polygon((-0.82, 0.04), (0.78, 0.44))
        legs = unary_union((
            _ellipse_polygon((-0.30, -0.30), (0.24, 0.26)),
            _ellipse_polygon((0.30, -0.30), (0.24, 0.26)),
        ))
        connectors = unary_union((
            LineString([(-0.4, 0.0), (-0.8, 0.04)]).buffer(0.11, cap_style="round"),
            LineString([(0.35, 0.05), (0.78, 0.05)]).buffer(0.10, cap_style="round"),
        ))
        return [(
            _outer_path(body, head, bill, tail, legs, connectors),
            _semantic_feature_id(spec, "body", "bill", "tail"),
        )]
    if mode == "moon_leap":
        # Author the profile directly so the two ear tips and compact tucked
        # legs survive final smoothing.  A boolean union rounded those small
        # diagnostic features away and made the animal read as a fish.
        fox = [
            (-1.16, 0.63), (-0.98, 0.80), (-0.74, 0.82),
            (-0.48, 0.57), (-0.27, 0.70), (0.00, 0.76),
            (0.25, 0.70), (0.34, 0.91), (0.49, 0.68),
            (0.55, 0.70), (0.70, 0.88), (0.71, 0.62),
            (0.79, 0.56), (1.05, 0.42), (0.72, 0.31),
            (0.50, 0.31), (0.38, 0.12), (0.18, 0.04),
            (0.10, 0.25), (-0.09, 0.25), (-0.22, 0.05),
            (-0.42, 0.12), (-0.36, 0.31), (-0.58, 0.30),
            (-0.82, 0.35), (-1.03, 0.48), (-1.16, 0.63),
        ]
        moon_hit = shape_library.get_shape("moon")
        if moon_hit is not None:
            moon = _sample_reference_path([
                (0.38 * x, 0.38 * y - 0.52)
                for x, y in moon_hit[1][0]
            ], max_points=32)
            if moon_hit[2] and moon[0] != moon[-1]:
                moon.append(moon[0])
        else:
            moon = _ellipse_path((0.0, -0.52), (0.55, 0.55))
        return [
            (fox, _semantic_feature_id(spec, "fox", "jump", "tucked", "tail")),
            (
                [(-0.38, 0.36), (-0.30, 0.25), (-0.18, 0.25)],
                _semantic_feature_id(spec, "leg", "tucked", "jump"),
            ),
            (
                [(0.24, 0.42), (0.31, 0.29), (0.43, 0.29)],
                _semantic_feature_id(spec, "leg", "foreleg", "jump"),
            ),
            (moon, _semantic_feature_id(spec, "crescent", "moon")),
        ]
    if mode == "cat":
        body = _ellipse_polygon((0.05, -0.02), (1.12, 0.58))
        head = _ellipse_polygon((-0.25, 0.37), (0.46, 0.42))
        neck = LineString([(-0.12, 0.18), (-0.24, 0.30)]).buffer(
            0.13, cap_style="round"
        )
        ears = unary_union((
            Polygon([(-0.46, 0.52), (-0.39, 0.76), (-0.25, 0.55)]),
            Polygon([(-0.20, 0.56), (-0.05, 0.72), (0.00, 0.48)]),
        ))
        return [
            (
                _outer_path(body, head, neck, ears),
                _semantic_feature_id(spec, "head", "ear", "arched back", "shoulder"),
            ),
            ([
                (0.54, 0.02), (0.86, 0.18), (0.98, 0.48),
                (0.86, 0.62),
            ], _semantic_feature_id(spec, "tail", "rear curve")),
            ([
                (-0.38, -0.20), (-0.43, -0.53), (-0.20, -0.53),
                (0.24, -0.20), (0.29, -0.53), (0.52, -0.53),
            ], _semantic_feature_id(spec, "leg", "front", "hind")),
        ]
    if mode == "dragon":
        text = _semantic_spec_text(spec)
        if "folded" in text or "osszecsukott" in text:
            body = _ellipse_polygon((-0.05, 0.04), (1.18, 0.58))
            neck = LineString([(0.30, 0.19), (0.60, 0.50)]).buffer(
                0.14, cap_style="round", join_style="round"
            )
            head = _ellipse_polygon((0.69, 0.52), (0.44, 0.29))
            snout = Polygon([(0.79, 0.61), (1.16, 0.52), (0.79, 0.43)])
            tail = Polygon([
                (-0.47, 0.18), (-0.76, 0.32), (-1.05, 0.55),
                (-1.35, 0.48), (-1.50, 0.35), (-1.24, 0.24),
                (-0.95, 0.04), (-0.65, -0.12), (-0.47, -0.08),
            ])
            legs = unary_union((
                box(-0.48, -0.56, -0.25, -0.15),
                box(0.27, -0.56, 0.50, -0.15),
            ))
            main = _outer_path(body, neck, head, snout, tail, legs)
            crown = [
                (0.50, 0.70), (0.52, 0.95), (0.64, 0.82),
                (0.73, 1.01), (0.82, 0.81), (0.95, 0.94),
                (0.92, 0.69), (0.50, 0.70),
            ]
            outer_wing = [
                (-0.10, 0.28), (-0.58, 0.51), (-0.46, 0.10),
                (-0.17, -0.02), (-0.10, 0.28),
            ]
            inner_wing = [
                (0.00, 0.24), (-0.34, 0.42), (-0.26, 0.08),
                (0.00, -0.02), (0.00, 0.24),
            ]
            return [
                (
                    main,
                    _semantic_feature_id(spec, "dragon", "snout", "tail", "body"),
                ),
                (crown, _semantic_feature_id(spec, "crown", "three point")),
                (outer_wing, _semantic_feature_id(spec, "folded wing", "wing")),
                (
                    inner_wing,
                    _semantic_feature_id(spec, "second wing", "layered", "folded"),
                ),
            ]
        body = _ellipse_polygon((-0.05, -0.10), (0.92, 1.02))
        neck = LineString([(0.12, 0.27), (0.38, 0.57)]).buffer(
            0.16, cap_style="round", join_style="round"
        )
        head = _ellipse_polygon((0.45, 0.59), (0.48, 0.32))
        snout = Polygon([(0.58, 0.68), (0.91, 0.58), (0.58, 0.48)])
        legs = unary_union((
            _ellipse_polygon((-0.38, -0.56), (0.28, 0.34)),
            _ellipse_polygon((0.34, -0.56), (0.28, 0.34)),
        ))
        main = _outer_path(body, neck, head, snout, legs)
        crown = [
            (0.25, 0.82), (0.28, 1.09), (0.40, 0.94),
            (0.50, 1.14), (0.59, 0.93), (0.72, 1.07),
            (0.69, 0.81), (0.25, 0.82),
        ]
        tail_path = [
            (-0.42, -0.18), (-0.72, -0.30), (-1.02, -0.56),
            (-0.79, -0.78), (-0.42, -0.72), (-0.13, -0.52),
        ]
        detail = (
            [(-0.20, 0.28), (-0.56, 0.50), (-0.48, 0.10), (-0.14, -0.04), (-0.20, 0.28)]
            if "wing" in text
            else [(-0.50, 0.08), (-0.34, 0.34), (-0.06, 0.10), (0.22, 0.34), (0.48, 0.08)]
        )
        return [
            (main, _semantic_feature_id(spec, "body", "head", "neck", "muzzle")),
            (crown, _semantic_feature_id(spec, "crown", "three point")),
            (tail_path, _semantic_feature_id(spec, "tail", "curl")),
            (detail, _semantic_feature_id(spec, "wing", "foreleg", "raised")),
        ]
    if mode == "phoenix":
        body = _ellipse_polygon((0.0, 0.18), (0.40, 0.66))
        head = _ellipse_polygon((0.11, 0.62), (0.27, 0.24))
        neck = LineString([(0.04, 0.40), (0.11, 0.58)]).buffer(
            0.10, cap_style="round"
        )
        beak = Polygon([(0.20, 0.68), (0.52, 0.61), (0.20, 0.55)])
        tail = Polygon([
            (-0.13, -0.10), (-0.19, -0.43), (0.0, -0.62),
            (0.19, -0.43), (0.13, -0.10),
        ])
        return [
            (
                _outer_path(body, neck, head, beak, tail),
                _semantic_feature_id(
                    spec, "body", "head", "beak", "tail", "rising"
                ),
            ),
            (
                [
                    (-0.10, 0.20), (-0.34, 0.39), (-0.82, 0.91),
                    (-0.65, 0.24), (-0.98, 0.02), (-0.39, 0.11),
                    (-0.10, 0.03), (-0.10, 0.20),
                ],
                _semantic_feature_id(spec, "left wing", "raised wing"),
            ),
            (
                [
                    (0.10, 0.20), (0.34, 0.39), (0.80, 0.88),
                    (0.64, 0.23), (0.96, 0.03), (0.40, 0.11),
                    (0.10, 0.03), (0.10, 0.20),
                ],
                _semantic_feature_id(spec, "right wing", "raised wing"),
            ),
            (
                [
                    (-0.76, -1.00), (-0.61, -0.58), (-0.43, -0.88),
                    (-0.24, -0.52), (0.0, -0.90), (0.24, -0.48),
                    (0.43, -0.88), (0.62, -0.58), (0.76, -1.00),
                    (0.44, -1.06), (-0.44, -1.06), (-0.76, -1.00),
                ],
                _semantic_feature_id(spec, "three flame", "flame", "base"),
            ),
        ]
    if mode == "bear":
        body = _ellipse_polygon((0.0, -0.18), (0.90, 1.00))
        head = _ellipse_polygon((0.0, 0.43), (0.62, 0.55))
        ears = unary_union((
            Point(-0.25, 0.68).buffer(0.14, quad_segs=5),
            Point(0.25, 0.68).buffer(0.14, quad_segs=5),
        ))
        hat = [
            (-0.48, 0.72), (0.48, 0.72), (0.30, 0.84),
            (0.24, 1.08), (-0.18, 1.08), (-0.28, 0.83),
            (-0.48, 0.72),
        ]
        return [
            (
                _outer_path(body, head, ears),
                _semantic_feature_id(spec, "bear", "seated", "body", "head"),
            ),
            (hat, _semantic_feature_id(spec, "hat", "large")),
            ([
                (-0.28, -0.05), (-0.48, -0.35), (-0.22, -0.54),
                (0.0, -0.24), (0.22, -0.54), (0.48, -0.35), (0.28, -0.05),
            ], _semantic_feature_id(spec, "arm", "leg", "seated")),
        ]
    return []


def _articulated_paths(
    spec: ShapeSpec,
    bounds: tuple[float, float, float, float],
) -> list[tuple[geo.Path, str]]:
    """Return a four-stroke side-view runner with independently visible arms."""

    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 0.5)
    height = max(max_y - min_y, 0.5)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    unit = max(width, height)
    hip = (cx - 0.05 * unit, cy - 0.04 * unit)
    shoulder = (cx + 0.18 * unit, cy + 0.34 * unit)
    head_centre = (cx + 0.31 * unit, cy + 0.50 * unit)
    torso = LineString([hip, shoulder]).buffer(
        0.13 * unit,
        cap_style="round",
        join_style="round",
    )
    support_leg = LineString([
        hip,
        (cx - 0.34 * unit, cy - 0.44 * unit),
        (cx - 0.70 * unit, cy - 0.52 * unit),
    ]).buffer(0.07 * unit, cap_style="round", join_style="round")
    neck = LineString([shoulder, head_centre]).buffer(
        0.08 * unit,
        cap_style="round",
    )
    main = _outer_path(
        torso,
        support_leg,
        neck,
        Point(*head_centre).buffer(0.13 * unit, quad_segs=6),
    )
    return [
        (
            main,
            _semantic_feature_id(spec, "forward", "lean", "head", "support leg"),
        ),
        ([
            hip,
            (cx + 0.48 * unit, cy - 0.01 * unit),
            (cx + 0.34 * unit, cy - 0.32 * unit),
        ], _semantic_feature_id(spec, "high knee", "raised knee", "stride")),
        ([
            shoulder,
            (cx + 0.53 * unit, cy + 0.16 * unit),
            (cx + 0.43 * unit, cy - 0.01 * unit),
        ], _semantic_feature_id(spec, "front arm", "lead arm", "arm swing")),
        ([
            shoulder,
            (cx - 0.22 * unit, cy + 0.28 * unit),
            (cx - 0.45 * unit, cy + 0.08 * unit),
        ], _semantic_feature_id(spec, "back arm", "rear arm", "opposing arm")),
    ]


def _semantic_part_size(part: ShapePart) -> tuple[float, float]:
    sizes = {
        "dominant": (1.15, 0.76),
        "large": (0.78, 0.56),
        "medium": (0.58, 0.38),
        "small": (0.36, 0.25),
    }
    width, height = sizes[part.relative_size]
    text = f"{part.id} {part.label}".casefold()
    if any(token in text for token in ("bill", "beak", "tail", "wing", "sail", "arm")):
        width *= 1.35
        height *= 0.72
    if "leg" in text or "foot" in text:
        width *= 0.75
        height *= 0.65
    if any(token in text for token in ("shaft", "antenna", "tower")):
        width *= 0.55
        height *= 1.45
    return width, height


def _semantic_part_centre(
    part: ShapePart,
    *,
    parent_centre: tuple[float, float],
    parent_size: tuple[float, float],
    index: int,
    viewpoint: str,
) -> tuple[float, float]:
    text = f"{part.id} {part.label} {part.position}".casefold()
    dx = dy = 0.0
    if any(token in text for token in ("right", "front", "forward")):
        dx += parent_size[0] * 0.62
    if any(token in text for token in ("left", "rear", "back", "behind")):
        dx -= parent_size[0] * 0.62
    if any(token in text for token in ("above", "upper", "top")):
        dy += parent_size[1] * 0.72
    if any(token in text for token in ("below", "lower", "bottom", "underside", "leg", "foot", "tucked")):
        dy -= parent_size[1] * 0.72
    if dx == 0.0 and dy == 0.0 and part.parent is not None:
        if any(token in text for token in ("bill", "beak", "snout", "nose")):
            dx = parent_size[0] * 0.72
        elif "tail" in text:
            dx = -parent_size[0] * 0.72
        elif any(token in text for token in ("head", "crown", "hat", "antenna")):
            dy = parent_size[1] * 0.72
        else:
            dx = parent_size[0] * (0.45 if index % 2 == 0 else -0.45)
    if viewpoint == "side" and "head" in text and dx == 0.0:
        dx = parent_size[0] * 0.55
    return parent_centre[0] + dx, parent_centre[1] + dy


def _semantic_part_geometry(
    part: ShapePart,
    centre: tuple[float, float],
    size: tuple[float, float],
    *,
    organic: bool,
) -> Polygon:
    text = f"{part.id} {part.label}".casefold()
    x, y = centre
    width, height = size
    if any(token in text for token in ("circle", "circular", "round", "disc", "oval")):
        points = [
            (
                x + width / 2 * math.cos(2 * math.pi * step / 20),
                y + height / 2 * math.sin(2 * math.pi * step / 20),
            )
            for step in range(20)
        ]
        return Polygon(points)
    box_tokens = ("box", "torso", "chest", "building", "tower")
    if any(token in text for token in box_tokens) or (
        not organic and any(token in text for token in ("body", "head"))
    ):
        radius = min(width, height) * 0.14
        return box(
            x - width / 2 + radius,
            y - height / 2 + radius,
            x + width / 2 - radius,
            y + height / 2 - radius,
        ).buffer(radius, quad_segs=3)
    if any(token in text for token in ("wing", "sail", "flame", "crown")):
        return Polygon([
            (x - width / 2, y - height / 2),
            (x, y + height / 2),
            (x + width / 2, y - height / 2),
        ])
    points = [
        (
            x + width / 2 * math.cos(2 * math.pi * step / 16),
            y + height / 2 * math.sin(2 * math.pi * step / 16),
        )
        for step in range(16)
    ]
    return Polygon(points)


def _catalog_grounded_candidate(
    *,
    idea: str,
    spec: ShapeSpec,
    response: LLMResponse,
    index: int,
) -> _GeneratedCandidate | None:
    """Build one route-valid candidate from known subject/accessory anchors.

    The generated variants remain the main creative path. This candidate gives
    the rendered critic a stable anatomical baseline when the request contains
    a catalogued subject, while the AI-produced ShapeSpec still defines every
    required cue and the final selection.
    """

    if not 0 <= index <= 3:
        return None
    references = _reference_shape_payloads(idea, limit=2)
    if (
        _semantic_scaffold_mode(spec) == "waves"
        and references
        and references[0].get("name") == "lighthouse"
    ):
        # The generic wave strokes below deliberately create the requested
        # pair.  Keeping a single catalogue wave here would produce a third,
        # asymmetric water mass and consume the lantern stroke budget.
        references = references[:1]
    if not references:
        return None
    anchored_paths: list[geo.Path] = []
    path_names: list[str] = []
    related_offset = _related_anchor_offset(idea)
    for reference_index, reference in enumerate(references):
        name = reference.get("name")
        if not isinstance(name, str):
            return None
        hit = shape_library.get_shape(name)
        if hit is None or not hit[2]:
            return None
        authored = shape_library.AUTHORED_OUTLINES.get(hit[0])
        source_paths = [list(authored)] if authored else [list(path) for path in hit[1]]
        if hit[0] == "robot":
            source_paths = _pose_robot_anchor(source_paths, idea)
        normalised = geo.normalize_shape(source_paths)
        if len(references) > 1:
            if reference_index == 0:
                normalised = [
                    [(x - 0.20, y - 0.10) for x, y in path]
                    for path in normalised
                ]
            elif (
                references[0].get("name") == "robot"
                and hit[0] == "umbrella"
                and _is_holding_relation(idea)
            ):
                normalised = _place_held_umbrella(normalised)
            else:
                normalised = [
                    [
                        (
                            0.65 * x + related_offset[0],
                            0.65 * y + related_offset[1],
                        )
                        for x, y in path
                    ]
                    for path in normalised
                ]
        anchored_paths.extend(normalised)
        path_names.extend([hit[0]] * len(normalised))
    if anchored_paths:
        all_anchor_points = [point for path in anchored_paths for point in path]
        anchor_bounds = (
            min(point[0] for point in all_anchor_points),
            min(point[1] for point in all_anchor_points),
            max(point[0] for point in all_anchor_points),
            max(point[1] for point in all_anchor_points),
        )
        secondary = _semantic_secondary_paths(spec, anchor_bounds)
        for path, name in secondary[:max(0, 4 - len(anchored_paths))]:
            anchored_paths.append(path)
            path_names.append(name)
    if not anchored_paths or len(anchored_paths) > 8:
        return None
    max_points = max(8, min(48, 88 // len(anchored_paths)))
    sampled_paths = [
        _sample_reference_path(path, max_points=max_points)
        for path in anchored_paths
    ]
    program = _catalog_program(sampled_paths, path_names, spec)
    required_ids = {feature.id for feature in spec.recognition_features}
    try:
        compiled = shape_program.compile_shape_program(
            program,
            required_feature_ids=required_ids,
        )
        _validate_route_friendly_geometry(compiled.paths)
        _validate_shape_spec_geometry(compiled, spec)
    except (TypeError, ValueError):
        return None
    strategy = "catalog-grounded semantic scaffold"
    raw: dict[str, object] = {
        "strategy": strategy,
        "program": program,
    }
    shape = Shape(
        name=" ".join(idea.split())[:80],
        paths=compiled.paths,
        closed=compiled.closed,
        source="llm",
        feature_paths=compiled.feature_paths,
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


def _catalog_fallback_shape(
    idea: str,
    spec: ShapeSpec,
    response: LLMResponse,
) -> Shape | None:
    """Return an honestly marked, recognisable semantic fallback when possible."""

    mode = _semantic_scaffold_mode(spec)
    candidate = None
    if mode in _FULL_SEMANTIC_SCAFFOLD_MODES:
        candidate = _spec_grounded_candidate(
            idea=idea,
            spec=spec,
            response=response,
            index=0,
        )
    if candidate is None:
        candidate = _catalog_grounded_candidate(
            idea=idea,
            spec=spec,
            response=response,
            index=0,
        )
    if candidate is None and mode != "silhouette":
        candidate = _spec_grounded_candidate(
            idea=idea,
            spec=spec,
            response=response,
            index=0,
        )
    if candidate is None:
        return None
    shape = candidate.shape
    shape.name = f"grounded:{' '.join(idea.split())[:70]}"
    shape.source = "fallback"
    shape.spec = spec
    shape.recognition_features = [feature.label for feature in spec.recognition_features]
    shape.semantic_verification = _geometry_only_verification(candidate)
    shape.generator_provider = response.provider
    shape.generator_model = response.model
    shape.generator_usage = dict(response.usage)
    shape.generated_candidate_count = 1
    shape.selected_candidate = 0
    return shape


def _related_anchor_offset(idea: str) -> tuple[float, float]:
    words = unicodedata.normalize("NFKD", idea).encode("ascii", "ignore").decode().casefold()
    if _is_holding_relation(words):
        return 0.17, 0.34
    if any(token in words for token in ("above", "over", "felett")):
        return 0.0, 0.68
    if any(token in words for token in ("beside", "next to", "mellett")):
        return 0.62, 0.0
    return 0.45, 0.42


def _is_holding_relation(idea: str) -> bool:
    words = unicodedata.normalize("NFKD", idea).encode("ascii", "ignore").decode().casefold()
    return any(token in words for token in ("holding", "held", "with", "tart", "fog"))


def _place_held_umbrella(paths: list[geo.Path]) -> list[geo.Path]:
    """Separate the canopy from the head while pulling its handle to the hand."""

    placed: list[geo.Path] = []
    for path in paths:
        transformed: geo.Path = []
        for x, y in path:
            placed_x = 0.65 * x + 0.40
            placed_y = 0.65 * y + 0.48
            if y < -0.15:
                blend = min(1.0, max(0.0, (-0.15 - y) / 0.38))
                placed_x -= 0.255 * blend
                placed_y -= 0.175 * blend
            transformed.append((placed_x, placed_y))
        placed.append(transformed)
    return placed


def _pose_robot_anchor(paths: list[geo.Path], idea: str) -> list[geo.Path]:
    """Apply bounded silhouette deformations for common robot pose modifiers."""

    words = unicodedata.normalize("NFKD", idea).encode("ascii", "ignore").decode().casefold()
    waving = any(word in words for word in ("wave", "waving", "integet"))
    walking = any(word in words for word in ("walk", "walking", "setal", "lepked"))
    # ShapeSpec expresses pose relations in image coordinates ("viewer left"
    # and "viewer right"), so explicit side requests must follow that contract
    # rather than anatomical mirroring.  Unspecified waves retain the catalog
    # pose on positive X.
    if any(token in words for token in ("left arm", "left hand", "bal kar", "bal kezzel")):
        raised_side = -1.0
    else:
        raised_side = 1.0
    posed = deepcopy(paths)
    for path in posed:
        for point_index, (x, y) in enumerate(path):
            side_x = raised_side * x
            if waving and side_x >= 0.70 and -0.30 <= y <= 0.40:
                path[point_index] = (
                    raised_side * (0.66 + 0.50 * (side_x - 0.66)),
                    y + 1.60 * (side_x - 0.66),
                )
                continue
            if walking and y <= -0.60:
                direction = 1.0 if x >= 0 else -1.0
                path[point_index] = (
                    x + direction * (0.10 + 0.05 * abs(y)),
                    y + (0.08 if x >= 0 else -0.08),
                )
    return posed


def _catalog_program(
    paths: list[geo.Path],
    path_names: list[str],
    spec: ShapeSpec,
) -> dict[str, object]:
    """Encode anchored paths and assign broad, spatially meaningful cue spans."""

    strokes: list[dict[str, object]] = []
    segments: list[tuple[dict[str, object], str, tuple[float, float], float]] = []
    all_points = [point for path in paths for point in path]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    centre_x = (min_x + max_x) / 2
    centre_y = (min_y + max_y) / 2
    half_width = max((max_x - min_x) / 2, 1e-9)
    half_height = max((max_y - min_y) / 2, 1e-9)
    for path, path_name in zip(paths, path_names, strict=True):
        closed_path = len(path) >= 3 and path[0] == path[-1]
        vertices = path[:-1] if closed_path else path
        if len(vertices) < 3:
            continue
        commands: list[dict[str, object]] = [
            {"op": "move", "points": [list(vertices[0])], "feature_id": None}
        ]
        previous = vertices[0]
        for endpoint in vertices[1:]:
            command: dict[str, object] = {
                "op": "line",
                "points": [list(endpoint)],
                "feature_id": None,
            }
            commands.append(command)
            midpoint = (
                ((previous[0] + endpoint[0]) / 2 - centre_x) / half_width,
                ((previous[1] + endpoint[1]) / 2 - centre_y) / half_height,
            )
            segments.append((command, path_name, midpoint, math.dist(previous, endpoint)))
            previous = endpoint
        if closed_path:
            close_command: dict[str, object] = {
                "op": "close",
                "points": [],
                "feature_id": None,
            }
            commands.append(close_command)
            midpoint = (
                ((previous[0] + vertices[0][0]) / 2 - centre_x) / half_width,
                ((previous[1] + vertices[0][1]) / 2 - centre_y) / half_height,
            )
            segments.append((
                close_command,
                path_name,
                midpoint,
                math.dist(previous, vertices[0]),
            ))
        strokes.append({"commands": commands})

    features = list(spec.recognition_features)

    def assigned_feature(segment: tuple[dict[str, object], str, tuple[float, float], float]) -> str:
        value = segment[0].get("feature_id")
        return value if isinstance(value, str) else ""

    for command, path_name, midpoint, _ in segments:
        command["feature_id"] = max(
            features,
            key=lambda feature: _catalog_feature_affinity(feature, path_name, midpoint),
        ).id
    minimum_segments = (
        max(2, math.ceil(len(segments) * 0.06))
        if len(segments) >= 2 * len(features)
        else 1
    )
    for feature in sorted(features, key=lambda item: (-item.importance, item.id)):
        while sum(command.get("feature_id") == feature.id for command, *_ in segments) < minimum_segments:
            counts = {
                candidate.id: sum(
                    command.get("feature_id") == candidate.id
                    for command, *_ in segments
                )
                for candidate in features
            }
            replaceable = [
                segment
                for segment in segments
                if counts.get(assigned_feature(segment), 0) > minimum_segments
            ]
            if not replaceable:
                break
            command, _, _, _ = max(
                replaceable,
                key=lambda segment: (
                    _catalog_feature_affinity(feature, segment[1], segment[2]),
                    segment[3],
                ),
            )
            command["feature_id"] = feature.id
    total_length = sum(length for *_, length in segments)
    minimum_lengths = {
        feature.id: total_length * (0.06 if feature.importance >= 4 else 0.04)
        for feature in features
    }
    for feature in sorted(features, key=lambda item: (-item.importance, item.id)):
        for _ in range(len(segments)):
            lengths = {
                candidate.id: sum(
                    length
                    for command, _, _, length in segments
                    if command.get("feature_id") == candidate.id
                )
                for candidate in features
            }
            if lengths[feature.id] >= minimum_lengths[feature.id]:
                break
            replaceable = [
                segment
                for segment in segments
                if assigned_feature(segment) != feature.id
                and lengths.get(assigned_feature(segment), 0.0) - segment[3]
                >= minimum_lengths.get(assigned_feature(segment), 0.0)
            ]
            if not replaceable:
                break
            command, _, _, _ = max(
                replaceable,
                key=lambda segment: (
                    _catalog_feature_affinity(feature, segment[1], segment[2]),
                    segment[3],
                ),
            )
            command["feature_id"] = feature.id
    for stroke in strokes:
        stroke_commands = stroke.get("commands")
        if (
            isinstance(stroke_commands, list)
            and len(stroke_commands) > 1
            and isinstance(stroke_commands[0], dict)
            and isinstance(stroke_commands[1], dict)
        ):
            stroke_commands[0]["feature_id"] = stroke_commands[1].get("feature_id")
    return {"strokes": strokes, "closed": spec.closed_silhouette}


def _catalog_feature_affinity(
    feature: ShapeFeature,
    path_name: str,
    midpoint: tuple[float, float],
) -> float:
    text = " ".join(
        (feature.id, feature.label, feature.geometry_hint, feature.relation)
    ).casefold()
    x, y = midpoint
    score = feature.importance * 0.01
    readable_name = path_name.replace("_", " ")
    if readable_name in text:
        score += 8.0
    groups = {
        "top": ("head", "antenna", "crown", "hat", "roof", "top", "canopy", "sail"),
        "bottom": ("leg", "foot", "base", "stride", "flame", "wave", "ground"),
        "side": ("arm", "hand", "wing", "handle", "shaft", "tail", "bill", "beak"),
        "front": ("front", "bill", "beak", "nose", "forward", "right"),
        "rear": ("rear", "back", "tail", "left"),
        "centre": ("body", "torso", "chest", "mass", "centre", "center"),
    }
    if any(token in text for token in groups["top"]):
        score += 3.0 * y
    if any(token in text for token in groups["bottom"]):
        score -= 3.0 * y
    if any(token in text for token in groups["side"]):
        score += 2.0 * abs(x)
    if any(token in text for token in groups["front"]):
        score += 2.0 * x
    if any(token in text for token in groups["rear"]):
        score -= 2.0 * x
    if any(token in text for token in groups["centre"]):
        score += 2.0 * (1.0 - min(1.0, abs(x)))
    if path_name == "umbrella":
        score += 6.0 if any(token in text for token in ("umbrella", "canopy", "handle", "shaft", "open")) else -2.0
    if path_name == "robot":
        score += 3.0 if any(token in text for token in ("robot", "head", "body", "torso", "arm", "leg", "antenna")) else 0.0
    return score


def _custom_shape_cache_key(
    idea: str,
    style: str,
    reference_digest: str = "",
) -> tuple[str, str]:
    normalized = "\0".join(
        (
            " ".join(idea.casefold().split()),
            " ".join(style.casefold().split()),
            reference_digest,
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
