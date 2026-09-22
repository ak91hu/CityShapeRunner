"""Final review cost, geometry binding, malformed answers and concurrency."""
import json

import pytest

from gps_art_wizzard.llm import LLMResponse
from gps_art_wizzard.state import Shape, SnappedRoute, Validation, WorkflowState
from gps_art_wizzard.tools import route_review


@pytest.fixture(autouse=True)
def clear_cache():
    route_review.clear_route_review_cache()
    yield
    route_review.clear_route_review_cache()


def state():
    return WorkflowState("heart", shape=Shape("heart", [], True, generator_provider="opencode"),
        snapped=SnappedRoute([(47.5, 19), (47.51, 19.01), (47.5, 19.02), (47.5, 19)], 4000, True),
        validation=Validation(0.8, 1, 1, 0.8))


def answer(**kwargs):
    return LLMResponse(json.dumps({"reviews": [{"index": 0, "recognized_subject": "triangle",
        "score": 0.4, "confidence": 0.9, "missing_features": ["heart notch"],
        "reason": "No visible notch"}]}), "opencode", "mini")


def test_repeated_route_uses_cache_and_geometry_change_requires_new_review(monkeypatch):
    calls = []

    def complete(*args, **kwargs):
        calls.append(kwargs)
        return answer()

    monkeypatch.setattr(route_review, "try_complete", complete)
    first = state()
    route_review.review_finalists(first)
    second = state()
    route_review.review_finalists(second)
    assert len(calls) == 1
    assert calls[0]["max_provider_attempts"] == 1
    assert calls[0]["max_tokens"] == 1200
    assert len(calls[0]["images"]) == 1
    assert not first.validation.routed_semantic_review["independent"]
    assert not first.validation.routed_semantic_review["calibrated"]
    assert first.validation.score == 0.8
    second.snapped.points[1] = (47.515, 19.01)
    route_review.review_finalists(second)
    assert len(calls) == 2
    assert first.validation.routed_semantic_review["route_hash"] != second.validation.routed_semantic_review["route_hash"]


def test_malformed_review_does_not_invent_score_or_retry(monkeypatch):
    calls = []

    def complete(*args, **kwargs):
        calls.append(1)
        return LLMResponse('{"reviews": []}', "opencode")

    monkeypatch.setattr(route_review, "try_complete", complete)
    item = state()
    route_review.review_finalists(item)
    route_review.review_finalists(item)
    assert calls == [1]
    assert item.validation.routed_semantic_review is None


def test_unrouted_preview_spends_no_ai_call(monkeypatch):
    monkeypatch.setattr(route_review, "try_complete", lambda *a, **kw: pytest.fail("unexpected call"))
    item = state()
    item.snapped.snapped = False
    route_review.review_finalists(item)
    assert item.validation.routed_semantic_review is None


def test_essential_mode_spends_no_route_review_call(monkeypatch):
    settings = route_review.get_settings()
    monkeypatch.setattr(settings.llm, "usage_mode", "essential")
    monkeypatch.setattr(settings.workflow, "ai_route_verifier_enabled", True)
    monkeypatch.setattr(
        route_review,
        "try_complete",
        lambda *a, **kw: pytest.fail("essential mode must not call route-review AI"),
    )

    item = state()
    route_review.review_finalists(item)

    assert item.validation.routed_semantic_review is None


@pytest.mark.parametrize("score", [True, float("nan"), -1, 2])
def test_invalid_numeric_review_is_rejected(score):
    response = answer()
    data = json.loads(response.text)
    data["reviews"][0]["score"] = score
    response.text = json.dumps(data)
    assert route_review._validated_reviews(response, 1) is None


def test_review_uses_authored_orientation_without_moving_the_route(monkeypatch):
    from gps_art_wizzard.state import RouteDraft
    item = state()
    original = list(item.snapped.points)
    item.route_draft = RouteDraft(47.5, 19, 500, 90, 0, 0, 0, [], True)
    rendered = []

    def render_image(points, rotation):
        rendered.append((points, rotation))
        return "data:image/png;base64,AA=="

    monkeypatch.setattr(route_review, "_route_image", render_image)
    monkeypatch.setattr(route_review, "try_complete", lambda *a, **kw: answer())
    route_review.review_finalists(item)
    assert rendered == [(original, 90)]
    assert item.snapped.points == original
