from __future__ import annotations

import base64
import json

import pytest

from gps_art_wizzard.agents.shape_agent import (
    ShapeAgent,
    _adaptive_candidate_count,
    _clear_custom_shape_cache,
    _heuristic_shape_spec,
    _normalise_close_commands,
    _reference_shape_payloads,
)
from gps_art_wizzard.ai_shape_benchmark import AI_SHAPE_BENCHMARK_CASES
from gps_art_wizzard.llm import LLMResponse
from gps_art_wizzard.llm import factory as llm_factory
from gps_art_wizzard.state import Intent, Plan, Shape, WorkflowState
from gps_art_wizzard.tools.shape_program import (
    compile_shape_program,
    render_paths_png_data_url,
)


def _spec_payload(*, ambiguity: float = 0.2) -> dict:
    return {
        "subject": "waving robot",
        "modifiers": ["waving"],
        "pose": "right arm raised",
        "viewpoint": "front",
        "parts": [
            {"id": "body", "label": "body", "parent": None, "required": True, "relative_size": "dominant", "position": "centre"},
            {"id": "head", "label": "box head", "parent": "body", "required": True, "relative_size": "large", "position": "above body"},
            {"id": "arm", "label": "raised arm", "parent": "body", "required": True, "relative_size": "medium", "position": "upper right"},
            {"id": "legs", "label": "two legs", "parent": "body", "required": True, "relative_size": "medium", "position": "below body"},
        ],
        "recognition_features": [
            {"id": "box_head", "label": "separate box-shaped head", "importance": 5, "geometry_hint": "wide top mass", "relation": "above torso"},
            {"id": "antenna", "label": "large central antenna", "importance": 4, "geometry_hint": "bold peak", "relation": "on top of head"},
            {"id": "raised_arm", "label": "one clearly raised arm", "importance": 5, "geometry_hint": "asymmetric outer contour", "relation": "rises from right shoulder"},
            {"id": "split_legs", "label": "two separated blocky legs", "importance": 5, "geometry_hint": "deep broad gap", "relation": "below torso"},
        ],
        "symmetry": "none",
        "preferred_strokes": 1,
        "closed_silhouette": True,
        "aspect_ratio": 1.0,
        "ambiguity": ambiguity,
    }


def _program(*, raised: bool) -> dict:
    arm_points = (
        ([2.8, 3.2], [3.6, 3.2], [2.8, 0.6])
        if raised
        else ([4.5, 0.8], [4.2, -1.2], [2.2, 0.3])
    )
    commands = [
        {"op": "move", "points": [[-2.0, 2.0]], "feature_id": "box_head"},
        {"op": "line", "points": [[-0.35, 2.0]], "feature_id": "box_head"},
        {"op": "line", "points": [[0.0, 3.2]], "feature_id": "antenna"},
        {"op": "line", "points": [[0.35, 2.0]], "feature_id": "antenna"},
        {"op": "line", "points": [[2.0, 2.0]], "feature_id": "box_head"},
        {"op": "line", "points": [[2.0, 1.25]], "feature_id": "box_head"},
        {"op": "line", "points": [list(arm_points[0])], "feature_id": "raised_arm"},
        {"op": "line", "points": [list(arm_points[1])], "feature_id": "raised_arm"},
        {"op": "line", "points": [list(arm_points[2])], "feature_id": "raised_arm"},
        {"op": "line", "points": [[1.45, 0.45]], "feature_id": "raised_arm"},
        {"op": "line", "points": [[1.45, -2.5]], "feature_id": "split_legs"},
        {"op": "line", "points": [[0.35, -2.5]], "feature_id": "split_legs"},
        {"op": "line", "points": [[0.35, -0.65]], "feature_id": "split_legs"},
        {"op": "line", "points": [[-0.35, -0.65]], "feature_id": "split_legs"},
        {"op": "line", "points": [[-0.35, -2.5]], "feature_id": "split_legs"},
        {"op": "line", "points": [[-1.45, -2.5]], "feature_id": "split_legs"},
        {"op": "line", "points": [[-1.45, 0.45]], "feature_id": "split_legs"},
        {"op": "line", "points": [[-2.7, 0.0]], "feature_id": "raised_arm"},
        {"op": "line", "points": [[-3.0, 0.8]], "feature_id": "raised_arm"},
        {"op": "line", "points": [[-2.0, 1.25]], "feature_id": "box_head"},
        {"op": "close", "points": [], "feature_id": "box_head"},
    ]
    return {"strokes": [{"commands": commands}], "closed": True}


def test_close_command_is_moved_after_all_authored_segments() -> None:
    program = _program(raised=True)
    commands = program["strokes"][0]["commands"]
    commands.insert(-3, commands.pop())

    normalised = _normalise_close_commands(program)

    assert normalised["strokes"][0]["commands"][-1]["op"] == "close"
    assert sum(
        command["op"] == "close"
        for command in normalised["strokes"][0]["commands"]
    ) == 1
    assert program["strokes"][0]["commands"][-1]["op"] != "close"


def _review(candidate_index: int, score: float) -> dict:
    return {
        "candidate_index": candidate_index,
        "score": score,
        "subject_match": score,
        "silhouette_quality": score,
        "route_readability": score,
        "cue_results": [
            {"feature_id": feature_id, "present": True, "score": score, "reason": "large and visible"}
            for feature_id in ("box_head", "antenna", "raised_arm", "split_legs")
        ],
        "missing_features": [],
        "wrong_relations": [],
        "repair_instructions": [],
    }


def test_shape_program_compiles_curves_tracks_features_and_renders_png():
    program = {
        "strokes": [{"commands": [
            {"op": "move", "points": [[-2, 0]], "feature_id": "body"},
            {"op": "curve", "points": [[-2, 2], [2, 2], [2, 0]], "feature_id": "body"},
            {"op": "line", "points": [[1, -1]], "feature_id": "tail"},
            {"op": "line", "points": [[0, -0.4]], "feature_id": "tail"},
            {"op": "line", "points": [[-1, -1]], "feature_id": "body"},
            {"op": "close", "points": [], "feature_id": "body"},
        ]}],
        "closed": True,
    }
    compiled = compile_shape_program(program, required_feature_ids={"body", "tail"})

    assert compiled.paths[0][0] == compiled.paths[0][-1]
    assert len(compiled.paths[0]) > 8
    assert set(compiled.feature_coverage) == {"body", "tail"}
    assert compiled.warnings == []
    data_url = render_paths_png_data_url(compiled.paths)
    assert data_url.startswith("data:image/png;base64,")
    assert base64.b64decode(data_url.split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")


def test_shape_program_rejects_invalid_command_arity():
    program = _program(raised=True)
    program["strokes"][0]["commands"][1]["points"] = []
    with pytest.raises(ValueError, match="line command needs 1 point"):
        compile_shape_program(program)


def test_candidate_count_adapts_to_ambiguity_and_is_bounded(monkeypatch):
    low = _heuristic_shape_spec("robot")
    low.ambiguity = 0.0
    low.modifiers = []
    low.parts = low.parts[:2]
    for feature in low.recognition_features:
        feature.relation = ""
    high = _heuristic_shape_spec("a robot holding an umbrella while skating")
    high.ambiguity = 0.95
    high.modifiers = ["holding umbrella", "skating", "waving"]

    assert _adaptive_candidate_count(low) == 2
    assert _adaptive_candidate_count(high) == 4


def test_compound_requests_supply_multiple_ordered_catalog_anchors():
    anchors = _reference_shape_payloads("a robot holding an umbrella beside a cat")
    assert [anchor["name"] for anchor in anchors] == ["robot", "umbrella", "cat"]
    assert anchors[0]["role"] == "primary_subject"
    assert all(anchor["role"] == "related_part" for anchor in anchors[1:])


def test_full_ai_drawing_pipeline_uses_independent_rendered_review(monkeypatch):
    _clear_custom_shape_cache()
    geometry = {
        "name": "waving robot",
        "variants": [
            {"strategy": "compact pose", "program": _program(raised=False)},
            {"strategy": "raised arm silhouette", "program": _program(raised=True)},
        ],
        "preferred_variant": 0,
    }
    verification = {
        "reviews": [_review(0, 0.72), _review(1, 0.91)],
        "recommended_candidate": 1,
    }
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse(json.dumps(verification), "reviewer", "vision-model"),
    ])
    calls = []

    def complete(*_args, **kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr("gps_art_wizzard.agents.shape_agent.try_complete", complete)
    state = WorkflowState(
        prompt="a robot waving in Budapest, about 8 km",
        intent=Intent("a robot waving", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )
    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.source == "llm"
    assert state.shape.spec is not None
    assert state.shape.generated_candidate_count == 2
    assert state.shape.selected_candidate == 1
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.independent is True
    assert state.shape.semantic_verification.provider == "reviewer"
    assert state.shape.semantic_verification.score == pytest.approx(0.91)
    assert len(calls[2]["images"]) == 2
    assert calls[2]["exclude_provider"] == "generator"
    assert calls[2]["pin_provider"] is False


def test_raster_reference_is_authoritative_for_spec_and_geometry_prompts(monkeypatch):
    _clear_custom_shape_cache()
    geometry = {
        "name": "mug icon",
        "variants": [
            {"strategy": "handle silhouette", "program": _program(raised=False)},
            {"strategy": "bold outline", "program": _program(raised=True)},
        ],
        "preferred_variant": 1,
    }
    responses = iter([
        LLMResponse(
            json.dumps({"spec": _spec_payload(), **geometry}),
            "generator",
            "vision-draw",
        ),
    ])
    calls = []

    def complete(*_args, **kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr("gps_art_wizzard.agents.shape_agent.try_complete", complete)
    data_url = "data:image/webp;base64,UklGRgQAAABXRUJQ"
    state = WorkflowState(
        prompt="a custom image in Budapest, about 10 km",
        intent=Intent("custom image", None, "Budapest", "run", 10, None),
        plan=Plan(shape_strategy="template"),
        reference_image_data_url=data_url,
        reference_name="mug icon",
        reference_kind="raster",
    )

    ShapeAgent().run(state)

    assert calls[0]["images"][0].data_url == data_url
    assert calls[0]["images"][0].detail == "auto"
    assert len(calls) == 1
    assert calls[0]["max_provider_attempts"] == 1
    assert "Treat the image as authoritative" in calls[0]["messages"][0]["content"]
    assert calls[0]["json_schema"]["required"] == [
        "spec",
        "name",
        "variants",
        "preferred_variant",
    ]
    assert state.shape is not None
    assert state.shape.name == "mug icon"


def test_visual_svg_uses_sampled_geometry_without_waiting_for_ai(monkeypatch):
    _clear_custom_shape_cache()

    def complete(*_args, **_kwargs):
        raise AssertionError("SVG geometry should bypass the visual model")

    monkeypatch.setattr("gps_art_wizzard.agents.shape_agent.try_complete", complete)
    fallback_shape = Shape(
        name="linked mug",
        paths=[[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0), (0.0, 0.0)]],
        closed=True,
        source="reference_svg",
    )
    state = WorkflowState(
        prompt="a custom image in Budapest, about 10 km",
        intent=Intent("custom image", None, "Budapest", "run", 10, None),
        plan=Plan(shape_strategy="template"),
        reference_shape=fallback_shape,
        reference_image_data_url="data:image/png;base64,aW1hZ2U=",
        reference_name="linked mug",
        reference_kind="svg",
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.name == "linked mug"
    assert state.shape.source == "reference_svg"
    assert len(state.shape.paths) == 1
    assert state.shape.paths[0][0] == state.shape.paths[0][-1]


def test_raster_reference_falls_back_to_local_contour_after_one_provider(monkeypatch):
    _clear_custom_shape_cache()
    calls = []

    def complete(fallback, **kwargs):
        calls.append(kwargs)
        return fallback()

    monkeypatch.setattr("gps_art_wizzard.agents.shape_agent.try_complete", complete)
    fallback_shape = Shape(
        name="linked mug",
        paths=[[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0), (0.0, 0.0)]],
        closed=True,
        source="reference_raster",
    )
    state = WorkflowState(
        prompt="a custom image in Budapest, about 10 km",
        intent=Intent("custom image", None, "Budapest", "run", 10, None),
        plan=Plan(shape_strategy="llm"),
        reference_shape=fallback_shape,
        reference_image_data_url="data:image/png;base64,aW1hZ2U=",
        reference_name="linked mug",
        reference_kind="raster",
    )

    ShapeAgent().run(state)

    assert len(calls) == 1
    assert calls[0]["max_provider_attempts"] == 1
    assert state.shape is not None
    assert state.shape.source == "reference_raster"


def test_weak_visual_review_triggers_one_targeted_repair(monkeypatch):
    _clear_custom_shape_cache()
    geometry = {
        "name": "waving robot",
        "variants": [
            {"strategy": "compact pose", "program": _program(raised=False)},
            {"strategy": "raised arm silhouette", "program": _program(raised=True)},
        ],
        "preferred_variant": 1,
    }
    weak = {
        "reviews": [_review(0, 0.5), _review(1, 0.55)],
        "recommended_candidate": 1,
    }
    strong = {"reviews": [_review(0, 0.9)], "recommended_candidate": 0}
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse(json.dumps(weak), "reviewer", "vision-model"),
        LLMResponse(
            json.dumps({"candidate": {"strategy": "repaired raised arm", "program": _program(raised=True)}}),
            "generator",
            "draw-model",
        ),
        LLMResponse(json.dumps(strong), "reviewer", "vision-model"),
    ])
    calls = []

    def complete(*_args, **kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr("gps_art_wizzard.agents.shape_agent.try_complete", complete)
    state = WorkflowState(
        prompt="a robot waving in Budapest, about 8 km",
        intent=Intent("a robot waving", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm"),
    )
    ShapeAgent().run(state)

    assert len(calls) == 5
    assert "typed diagnostics" in calls[3]["messages"][0]["content"]
    assert state.shape is not None
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.9)


def test_ai_shape_benchmark_covers_multilingual_and_hard_cases():
    assert len(AI_SHAPE_BENCHMARK_CASES) >= 20
    assert {case.language for case in AI_SHAPE_BENCHMARK_CASES} >= {"en", "hu", "de", "fr"}
    categories = {case.category for case in AI_SHAPE_BENCHMARK_CASES}
    assert {"relationship", "pose", "rare", "ambiguous", "multilingual"} <= categories


def test_visual_reviewer_excludes_generator_without_replacing_sticky_provider(monkeypatch):
    class Provider:
        def __init__(self, name):
            self.name = name

        def is_available(self):
            return True

        def complete(self, **_kwargs):
            return LLMResponse("{}", self.name, f"{self.name}-model")

    generator = Provider("generator")
    reviewer = Provider("reviewer")
    monkeypatch.setattr(llm_factory, "available_providers", lambda: (generator, reviewer))
    llm_factory.reset_sticky()
    try:
        first = llm_factory.try_complete(lambda: None, messages=[])
        review = llm_factory.try_complete(
            lambda: None,
            messages=[],
            exclude_provider="generator",
            pin_provider=False,
        )
        again = llm_factory.try_complete(lambda: None, messages=[])
    finally:
        llm_factory.reset_sticky()

    assert (first.provider, review.provider, again.provider) == (
        "generator",
        "reviewer",
        "generator",
    )


def test_provider_attempt_limit_prevents_slow_fallback_cascade(monkeypatch):
    class Provider:
        def __init__(self, name):
            self.name = name
            self.calls = 0

        def is_available(self):
            return True

        def complete(self, **_kwargs):
            self.calls += 1
            raise llm_factory.LLMError("timed out")

    primary = Provider("primary")
    secondary = Provider("secondary")
    monkeypatch.setattr(llm_factory, "available_providers", lambda: (primary, secondary))
    llm_factory.reset_sticky()
    try:
        response = llm_factory.try_complete(
            lambda: "local contour",
            messages=[],
            max_provider_attempts=1,
        )
    finally:
        llm_factory.reset_sticky()

    assert response == "local contour"
    assert primary.calls == 1
    assert secondary.calls == 0
