"""Bounded, cached visual review of exact final street geometries.

One provider attempt reviews at most three finalists. The same provider may
review its generated shape, but this is disclosed as non-independent. Semantic
judgement is advisory until calibrated by human benchmark labels; it never
overrides routing evidence or geometric quality gates.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import threading
import time
from collections import OrderedDict

from ..config import get_settings
from ..llm import ImageInput, LLMResponse, extract_json, try_complete
from ..prompts import render
from ..state import WorkflowState
from . import geo, shape_program

_VERSION = "route-review-v1"
_CACHE: OrderedDict[str, tuple[float, dict | None]] = OrderedDict()
_LOCK = threading.Lock()
_FLIGHTS = [threading.Lock() for _ in range(32)]
_MAX_CACHE = 512


def clear_route_review_cache():
    with _LOCK:
        _CACHE.clear()


def _cache_get(key):
    with _LOCK:
        value = _CACHE.get(key)
        if value and value[0] > time.monotonic():
            _CACHE.move_to_end(key)
            return True, copy.deepcopy(value[1])
        _CACHE.pop(key, None)
        return False, None


def _cache_put(key, value):
    with _LOCK:
        _CACHE[key] = (time.monotonic() + (86400 if value else 60), copy.deepcopy(value))
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_CACHE:
            _CACHE.popitem(last=False)


def _route_image(points, rotation_deg=0.0):
    center = points[0]
    authored_frame = geo.rotate_shape(
        [[geo.latlon_to_unit(*point, *center, 1) for point in points]],
        -math.radians(rotation_deg),
    )
    return shape_program.render_paths_png_data_url(
        geo.normalize_shape(authored_frame),
        size=256,
    )


def _schema(count):
    item = {"type": "object", "additionalProperties": False, "properties": {
        "index": {"type": "integer", "minimum": 0, "maximum": count - 1},
        "recognized_subject": {"type": "string", "maxLength": 120},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "missing_features": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 120}},
        "reason": {"type": "string", "maxLength": 240},
    }}
    item["required"] = list(item["properties"])
    return {"type": "object", "additionalProperties": False, "properties": {
        "reviews": {"type": "array", "minItems": count, "maxItems": count, "items": item}},
        "required": ["reviews"]}


def _validated_reviews(response, count):
    payload = extract_json(response.text)
    rows = payload.get("reviews") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != count:
        return None
    checked = {}
    for row in rows:
        if not isinstance(row, dict):
            return None
        index = row.get("index")
        if type(index) is not int or index not in range(count) or index in checked:
            return None
        for name in ("score", "confidence"):
            number = row.get(name)
            if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1:
                return None
        if any(not isinstance(row.get(key), str) for key in ("recognized_subject", "reason")):
            return None
        missing = row.get("missing_features")
        if not isinstance(missing, list) or len(missing) > 6 or any(not isinstance(item, str) for item in missing):
            return None
        checked[index] = {"score": row["score"], "confidence": row["confidence"],
                          "recognized_subject": row["recognized_subject"][:120],
                          "missing_features": [item[:120] for item in missing],
                          "reason": row["reason"][:240]}
    return checked


def review_finalists(state: WorkflowState) -> None:
    settings = get_settings()
    if (
        settings.llm.usage_mode == "essential"
        or not settings.workflow.ai_route_verifier_enabled
        or not state.shape
        or not state.snapped
        or not state.snapped.snapped
        or not state.validation
    ):
        return
    from ..quality import passes_quality_gates
    # Selected geometry first. A review is attached only to matching geometry,
    # including copies of the selected candidate in the candidate collection.
    finalists = [(state.snapped.points, state.validation, state.route_draft.rotation_deg if state.route_draft else 0.0)]
    limit = min(3, max(1, settings.workflow.ai_route_verifier_candidates))
    for candidate in sorted(state.candidates, key=lambda c: (
        passes_quality_gates(c.validation, closed=c.closed), c.validation.score), reverse=True):
        if len(finalists) >= limit:
            break
        if candidate.snapped and candidate.shape_name == state.shape.name and not any(candidate.points == points for points, _, _ in finalists):
            finalists.append((candidate.points, candidate.validation, candidate.rotation_deg))
    llm = settings.llm
    context = {"subject": state.shape.name, "features": state.shape.recognition_features,
               "generator": state.shape.generator_provider,
               "provider": llm.provider, "models": [llm.model, llm.opencode_model, llm.opencode_structured_model,
                  llm.openai_model, llm.anthropic_model, llm.ollama_model], "version": _VERSION}
    keys = [hashlib.sha256(json.dumps([context, points, rotation], sort_keys=True, allow_nan=False).encode()).hexdigest()
            for points, _, rotation in finalists]
    # Acquire striped locks in a stable order to collapse identical concurrent
    # requests without deadlocks. Cache lookup is repeated after acquisition.
    locks = [_FLIGHTS[index] for index in sorted({int(key[:8], 16) % len(_FLIGHTS) for key in keys})]
    acquired = []
    try:
        for lock in locks:
            if not lock.acquire(timeout=0.05):
                state.history.append({"agent": "route_review", "status": "concurrent_review_pending"})
                return
            acquired.append(lock)
        cached = [_cache_get(key) for key in keys]
        missing = [i for i, (found, _) in enumerate(cached) if not found]
        if missing:
            response = try_complete(
                lambda: LLMResponse("{}", "fallback"),
                messages=[{"role": "user", "content": render("route_review",
                    subject=json.dumps(state.shape.name, ensure_ascii=False),
                    features=json.dumps(state.shape.recognition_features, ensure_ascii=False))}],
                images=[ImageInput(_route_image(finalists[i][0], finalists[i][2]), detail="low") for i in missing],
                json_mode=True, json_schema=_schema(len(missing)), temperature=0,
                max_tokens=1200, max_provider_attempts=1, pin_provider=False,
            )
            try:
                reviews = _validated_reviews(response, len(missing)) if response.provider != "fallback" else None
            except (ValueError, TypeError, KeyError):
                reviews = None
            for index, finalist_index in enumerate(missing):
                review = reviews[index] if reviews else None
                if review is not None:
                    review.update(provider=response.provider, model=response.model,
                                  independent=response.provider != state.shape.generator_provider,
                                  route_hash=keys[finalist_index], method="rendered_street_route",
                                  calibrated=False)
                _cache_put(keys[finalist_index], review)
                cached[finalist_index] = (True, review)
        for (points, validation, _), (_, review) in zip(finalists, cached, strict=True):
            validation.routed_semantic_review = copy.deepcopy(review)
            if review and review["score"] < 0.65 and review["confidence"] >= 0.7:
                issue = "visual review: the final street outline may not depict the requested subject"
                if issue not in validation.issues:
                    validation.issues.append(issue)
            for candidate in state.candidates:
                if candidate.points == points and candidate.shape_name == state.shape.name:
                    candidate.validation.routed_semantic_review = copy.deepcopy(review)
        state.history.append({"agent": "route_review", "finalists": len(finalists),
                              "uncached_finalists": len(missing),
                              "reviewed": sum(review is not None for _, review in cached)})
    finally:
        for lock in reversed(acquired):
            lock.release()
