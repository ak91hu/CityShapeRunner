from __future__ import annotations

import base64
import json

import pytest

from gps_art_wizzard.agents.shape_agent import (
    ShapeAgent,
    _adaptive_candidate_count,
    _candidate_from_program,
    _catalog_grounded_candidate,
    _clear_custom_shape_cache,
    _final_ai_preview_paths,
    _fit_program_aspect,
    _heuristic_shape_spec,
    _linearise_curves,
    _normalise_close_commands,
    _reference_shape_payloads,
    _shape_spec_from_response,
    _spec_grounded_candidate,
    _split_embedded_moves,
    _untangle_linear_outline,
)
from gps_art_wizzard.ai_shape_benchmark import AI_SHAPE_BENCHMARK_CASES, passes_ai_shape_quality
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


def _platypus_spec_payload() -> dict:
    return {
        "subject": "platypus",
        "modifiers": ["wide bill", "broad tail"],
        "pose": "side profile",
        "viewpoint": "side",
        "parts": [
            {"id": "body", "label": "long body", "parent": None, "required": True, "relative_size": "dominant", "position": "centre"},
            {"id": "head", "label": "small head", "parent": "body", "required": True, "relative_size": "medium", "position": "front upper"},
            {"id": "bill", "label": "wide flat bill", "parent": "head", "required": True, "relative_size": "medium", "position": "front"},
            {"id": "tail", "label": "broad paddle tail", "parent": "body", "required": True, "relative_size": "large", "position": "rear"},
            {"id": "legs", "label": "short legs", "parent": "body", "required": True, "relative_size": "small", "position": "below"},
        ],
        "recognition_features": [
            {"id": "long_body", "label": "long low body", "importance": 5, "geometry_hint": "smooth low oval centre", "relation": "between head and tail"},
            {"id": "wide_bill", "label": "wide flat bill", "importance": 5, "geometry_hint": "front projection", "relation": "in front of head"},
            {"id": "broad_tail", "label": "broad paddle tail", "importance": 5, "geometry_hint": "wide rear lobe", "relation": "behind body"},
            {"id": "short_legs", "label": "short low legs", "importance": 3, "geometry_hint": "small lower mass", "relation": "below body"},
        ],
        "symmetry": "none",
        "preferred_strokes": 1,
        "closed_silhouette": True,
        "aspect_ratio": 1.8,
        "ambiguity": 0.25,
    }


def _semantic_stroke_spec_payload(mode: str) -> dict:
    common = {
        "modifiers": [],
        "viewpoint": "symbolic",
        "symmetry": "none",
        "preferred_strokes": 3,
        "closed_silhouette": True,
        "aspect_ratio": 1.1,
        "ambiguity": 0.35,
    }
    if mode == "spiral":
        return common | {
            "subject": "spiral galaxy",
            "pose": "two broad spiral arms around a core",
            "parts": [
                {"id": "core", "label": "round core", "parent": None, "required": True, "relative_size": "medium", "position": "centre"},
                {"id": "arm_a", "label": "first spiral arm", "parent": "core", "required": True, "relative_size": "large", "position": "curving outward"},
                {"id": "arm_b", "label": "second spiral arm", "parent": "core", "required": True, "relative_size": "large", "position": "opposite curving outward"},
            ],
            "recognition_features": [
                {"id": "core", "label": "compact round core", "importance": 4, "geometry_hint": "small oval", "relation": "at centre"},
                {"id": "arm_a", "label": "first broad spiral arm", "importance": 5, "geometry_hint": "open expanding arc", "relation": "from core"},
                {"id": "arm_b", "label": "second broad spiral arm", "importance": 5, "geometry_hint": "opposite open expanding arc", "relation": "from core"},
            ],
            "closed_silhouette": False,
        }
    if mode == "waves":
        return common | {
            "subject": "lighthouse above two waves",
            "pose": "upright above crashing waves",
            "parts": [
                {"id": "tower", "label": "lighthouse tower", "parent": None, "required": True, "relative_size": "dominant", "position": "centre"},
                {"id": "lantern", "label": "lantern roof", "parent": "tower", "required": True, "relative_size": "small", "position": "above"},
                {"id": "wave_left", "label": "left wave", "parent": None, "required": True, "relative_size": "large", "position": "below left"},
                {"id": "wave_right", "label": "right wave", "parent": None, "required": True, "relative_size": "large", "position": "below right"},
            ],
            "recognition_features": [
                {"id": "lantern", "label": "large lantern roof", "importance": 5, "geometry_hint": "wide cap", "relation": "above tower"},
                {"id": "wave_left", "label": "left crashing wave", "importance": 5, "geometry_hint": "bold crest", "relation": "below left"},
                {"id": "wave_right", "label": "right crashing wave", "importance": 5, "geometry_hint": "bold crest", "relation": "below right"},
            ],
        }
    if mode == "radial":
        return common | {
            "subject": "antique astrolabe",
            "pose": "hanging vertically by a ring",
            "viewpoint": "front",
            "preferred_strokes": 1,
            "aspect_ratio": 1.0,
            "parts": [
                {"id": "body", "label": "circular astrolabe body", "parent": None, "required": True, "relative_size": "dominant", "position": "center"},
                {"id": "ring", "label": "hanging suspension ring", "parent": "body", "required": True, "relative_size": "small", "position": "above attached at top"},
                {"id": "inner_lattice", "label": "inner radial lattice", "parent": "body", "required": False, "relative_size": "medium", "position": "inside body"},
                {"id": "index_arm", "label": "radial index arm", "parent": "body", "required": False, "relative_size": "small", "position": "from center toward lower edge"},
            ],
            "recognition_features": [
                {"id": "disc", "label": "round instrument disc", "importance": 5, "geometry_hint": "large circle", "relation": "outer body"},
                {"id": "ring", "label": "top hanging ring", "importance": 5, "geometry_hint": "small loop", "relation": "attached above"},
                {"id": "lattice", "label": "interior spoke lattice", "importance": 4, "geometry_hint": "radial openings", "relation": "inside disc"},
                {"id": "pointer", "label": "single index arm", "importance": 3, "geometry_hint": "straight radial pointer", "relation": "from centre"},
            ],
        }
    if mode == "articulated":
        return common | {
            "subject": "runner",
            "pose": "leaning forward with one knee raised",
            "viewpoint": "side",
            "preferred_strokes": 1,
            "closed_silhouette": False,
            "parts": [
                {"id": "torso", "label": "leaning torso", "parent": None, "required": True, "relative_size": "large", "position": "forward"},
                {"id": "head", "label": "head", "parent": "torso", "required": True, "relative_size": "medium", "position": "ahead"},
                {"id": "arms", "label": "opposing arms", "parent": "torso", "required": True, "relative_size": "medium", "position": "front and back"},
                {"id": "legs", "label": "split running legs", "parent": "torso", "required": True, "relative_size": "large", "position": "one knee raised and one back"},
            ],
            "recognition_features": [
                {"id": "lean", "label": "strong forward body lean", "importance": 5, "geometry_hint": "diagonal torso", "relation": "ahead of hips"},
                {"id": "knee", "label": "one high raised knee", "importance": 5, "geometry_hint": "bent front leg", "relation": "separate from support leg"},
                {"id": "stride", "label": "split running stride", "importance": 4, "geometry_hint": "back leg extended", "relation": "opposes knee"},
                {"id": "arms", "label": "opposing arm pump", "importance": 3, "geometry_hint": "bent arms", "relation": "counterbalances legs"},
            ],
        }
    raise AssertionError(f"unsupported semantic stroke mode {mode}")


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


def test_embedded_moves_are_split_into_explicit_strokes() -> None:
    program = {
        "strokes": [{"commands": [
            {"op": "move", "points": [[-2, 0]], "feature_id": "body"},
            {"op": "line", "points": [[-1, 1]], "feature_id": "body"},
            {"op": "line", "points": [[0, 0]], "feature_id": "body"},
            {"op": "close", "points": [], "feature_id": "body"},
            {"op": "move", "points": [[1, 0]], "feature_id": "accessory"},
            {"op": "line", "points": [[2, 1]], "feature_id": "accessory"},
            {"op": "line", "points": [[3, 0]], "feature_id": "accessory"},
            {"op": "close", "points": [], "feature_id": "accessory"},
        ]}],
        "closed": True,
    }

    split = _split_embedded_moves(program)
    compiled = compile_shape_program(split, required_feature_ids={"body", "accessory"})

    assert len(split["strokes"]) == 2
    assert len(compiled.paths) == 2
    assert compiled.warnings == []
    assert len(program["strokes"]) == 1


def test_closed_program_keeps_explicit_secondary_stroke_open() -> None:
    program = {
        "strokes": [
            {"commands": [
                {"op": "move", "points": [[-1, -1]], "feature_id": "body"},
                {"op": "line", "points": [[1, -1]], "feature_id": "body"},
                {"op": "line", "points": [[0, 1]], "feature_id": "body"},
                {"op": "close", "points": [], "feature_id": "body"},
            ]},
            {"commands": [
                {"op": "move", "points": [[-0.5, 0]], "feature_id": "detail"},
                {"op": "line", "points": [[0, 0.5]], "feature_id": "detail"},
                {"op": "line", "points": [[0.5, 0]], "feature_id": "detail"},
            ]},
        ],
        "closed": True,
    }

    compiled = compile_shape_program(program)
    preview = _final_ai_preview_paths(compiled.paths, compiled.closed)

    assert compiled.paths[0][0] == compiled.paths[0][-1]
    assert compiled.paths[1][0] != compiled.paths[1][-1]
    assert preview[0][0] == preview[0][-1]
    assert preview[1][0] != preview[1][-1]


@pytest.mark.parametrize(
    ("mode", "expected_paths"),
    [("spiral", 3), ("waves", 4), ("radial", 4)],
)
def test_spec_scaffold_preserves_semantic_secondary_strokes(
    mode: str,
    expected_paths: int,
) -> None:
    spec = _shape_spec_from_response(
        LLMResponse(
            json.dumps(_semantic_stroke_spec_payload(mode)),
            "generator",
            "spec-model",
        ),
        mode,
    )

    candidate = _spec_grounded_candidate(
        idea=spec.subject,
        spec=spec,
        response=LLMResponse("{}", "generator", "draw-model"),
        index=0,
    )

    assert candidate is not None
    assert len(candidate.shape.paths) == expected_paths
    assert candidate.shape.paths[0][0] == candidate.shape.paths[0][-1]
    if mode == "radial":
        assert all(path[0] == path[-1] for path in candidate.shape.paths)
    elif mode == "waves":
        assert all(path[0] != path[-1] for path in candidate.shape.paths[1:3])
        assert candidate.shape.paths[3][0] == candidate.shape.paths[3][-1]
    else:
        assert all(path[0] == path[-1] for path in candidate.shape.paths)
    assert not candidate.feature_warnings


def test_open_runner_scaffold_uses_bounded_articulated_strokes() -> None:
    spec = _shape_spec_from_response(
        LLMResponse(
            json.dumps(_semantic_stroke_spec_payload("articulated")),
            "generator",
            "spec-model",
        ),
        "runner",
    )

    candidate = _spec_grounded_candidate(
        idea=spec.subject,
        spec=spec,
        response=LLMResponse("{}", "generator", "draw-model"),
        index=0,
    )

    assert candidate is not None
    assert not candidate.shape.closed
    assert len(candidate.shape.paths) == 4
    assert candidate.shape.paths[0][0] == candidate.shape.paths[0][-1]
    assert all(path[0] != path[-1] for path in candidate.shape.paths[1:])
    assert not candidate.feature_warnings


@pytest.mark.parametrize(
    ("idea", "expected_paths"),
    [
        ("bold key with a large round bow and one tooth", 2),
        ("sailboat", 4),
        ("bicycle with flower basket", 4),
        ("platypus", 1),
        ("fox jumping over crescent moon", 4),
        ("robot holding an open umbrella", 4),
        ("antique astrolabe with a hanging ring", 4),
        ("spiral galaxy with two broad arms", 3),
        ("cat looking over its shoulder", 3),
        ("dragon wearing crown", 4),
        ("phoenix rising from flames", 4),
        ("teddy bear with large hat", 3),
        ("coffee cup with a handle and three steam curls", 4),
    ],
)
def test_typed_semantic_scaffolds_are_route_valid(
    idea: str,
    expected_paths: int,
) -> None:
    spec = _heuristic_shape_spec(idea)

    candidate = _spec_grounded_candidate(
        idea=idea,
        spec=spec,
        response=LLMResponse("{}", "generator", "draw-model"),
        index=0,
    )

    assert candidate is not None
    assert len(candidate.shape.paths) == expected_paths
    assert candidate.feature_warnings == []


def test_extreme_program_aspect_is_fitted_by_shrinking_only_long_axis() -> None:
    program = {
        "strokes": [{"commands": [
            {"op": "move", "points": [[-5, -0.5]], "feature_id": "body"},
            {"op": "line", "points": [[5, -0.5]], "feature_id": "head"},
            {"op": "line", "points": [[5, 0.5]], "feature_id": "head"},
            {"op": "line", "points": [[0, 0.7]], "feature_id": "body"},
            {"op": "line", "points": [[-5, 0.5]], "feature_id": "body"},
            {"op": "close", "points": [], "feature_id": "body"},
        ]}],
        "closed": True,
    }

    fitted = _fit_program_aspect(program, 2.0)
    compiled = compile_shape_program(fitted)
    points = compiled.paths[0]
    width = max(point[0] for point in points) - min(point[0] for point in points)
    height = max(point[1] for point in points) - min(point[1] for point in points)

    assert width / height == pytest.approx(2.0)
    assert height == pytest.approx(1.2)
    assert program["strokes"][0]["commands"][0]["points"] == [[-5, -0.5]]


def test_looping_cubic_can_fall_back_to_its_simple_labelled_endpoints() -> None:
    program = {
        "strokes": [{"commands": [
            {"op": "move", "points": [[-1, -1]], "feature_id": "body"},
            {"op": "curve", "points": [[3, 3], [-3, 3], [1, -1]], "feature_id": "body"},
            {"op": "line", "points": [[1, 1]], "feature_id": "head"},
            {"op": "line", "points": [[-1, 1]], "feature_id": "head"},
            {"op": "line", "points": [[-1, 0]], "feature_id": "body"},
            {"op": "close", "points": [], "feature_id": "body"},
        ]}],
        "closed": True,
    }
    curved = compile_shape_program(program)
    linear_program = _linearise_curves(program)
    linear = compile_shape_program(linear_program)

    from shapely.geometry import LineString

    assert not LineString(curved.paths[0]).is_simple
    assert LineString(linear.paths[0]).is_simple
    assert linear_program["strokes"][0]["commands"][1] == {
        "op": "line",
        "points": [[1, -1]],
        "feature_id": "body",
    }
    assert program["strokes"][0]["commands"][1]["op"] == "curve"


def test_crossed_linear_outline_can_be_untangled_without_dropping_cues() -> None:
    program = {
        "strokes": [{"commands": [
            {"op": "move", "points": [[-2, -1]], "feature_id": "box_head"},
            {"op": "line", "points": [[2, 1]], "feature_id": "antenna"},
            {"op": "line", "points": [[2, -1]], "feature_id": "raised_arm"},
            {"op": "line", "points": [[-2, 1]], "feature_id": "split_legs"},
            {"op": "line", "points": [[-2.5, 0]], "feature_id": "box_head"},
            {"op": "close", "points": [], "feature_id": "box_head"},
        ]}],
        "closed": True,
    }
    crossed = compile_shape_program(program)
    untangled_program = _untangle_linear_outline(program)
    untangled = compile_shape_program(
        untangled_program,
        required_feature_ids={"box_head", "antenna", "raised_arm", "split_legs"},
    )
    response = LLMResponse("{}", "generator", "draw-model")
    candidate = _candidate_from_program(
        {"strategy": "crossed outline", "program": program},
        0,
        "waving robot",
        _shape_spec_from_response(
            LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
            "waving robot",
        ),
        response,
    )

    from shapely.geometry import LineString

    assert not LineString(crossed.paths[0]).is_simple
    assert LineString(untangled.paths[0]).is_simple
    assert set(untangled.feature_coverage) == {
        "box_head", "antenna", "raised_arm", "split_legs",
    }
    assert LineString(candidate.shape.paths[0]).is_simple
    assert program["strokes"][0]["commands"][1]["points"] == [[2, 1]]


def _review(
    candidate_index: int,
    score: float,
    *,
    absent: set[str] | None = None,
    missing: list[str] | None = None,
    wrong_relations: list[str] | None = None,
) -> dict:
    absent = absent or set()
    return {
        "candidate_index": candidate_index,
        "score": score,
        "subject_match": score,
        "silhouette_quality": score,
        "route_readability": score,
        "cue_results": [
            {
                "feature_id": feature_id,
                "present": feature_id not in absent,
                "score": score if feature_id not in absent else 0.0,
                "reason": "large and visible" if feature_id not in absent else "not visible",
            }
            for feature_id in ("box_head", "antenna", "raised_arm", "split_legs")
        ],
        "missing_features": missing or [],
        "wrong_relations": wrong_relations or [],
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


def test_catalog_grounded_candidate_preserves_pose_cues_and_feature_spans() -> None:
    spec = _shape_spec_from_response(
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        "a robot waving",
    )
    candidate = _catalog_grounded_candidate(
        idea="a robot waving with its left arm",
        spec=spec,
        response=LLMResponse("{}", "generator", "draw-model"),
        index=0,
    )
    compound = _catalog_grounded_candidate(
        idea="a robot holding an open umbrella",
        spec=spec,
        response=LLMResponse("{}", "generator", "draw-model"),
        index=1,
    )

    assert candidate is not None
    assert candidate.feature_warnings == []
    assert set(candidate.shape.feature_paths) == {
        "box_head", "antenna", "raised_arm", "split_legs",
    }
    assert compound is not None
    assert len(compound.shape.paths) == 3
    assert compound.feature_warnings == []
    from shapely.geometry import LineString

    assert LineString(compound.shape.paths[0]).distance(
        LineString(compound.shape.paths[1])
    ) == pytest.approx(0.0)


def test_shapespec_grounded_candidate_composes_unknown_subject_parts() -> None:
    spec = _shape_spec_from_response(
        LLMResponse(json.dumps(_platypus_spec_payload()), "generator", "spec-model"),
        "a platypus with a wide bill and broad tail",
    )
    candidate = _spec_grounded_candidate(
        idea="a platypus with a wide bill and broad tail",
        spec=spec,
        response=LLMResponse("{}", "generator", "draw-model"),
        index=0,
    )

    assert candidate is not None
    assert candidate.feature_warnings == []
    assert set(candidate.shape.feature_paths) == {
        "long_body", "wide_bill", "broad_tail", "short_legs",
    }
    from shapely.geometry import LineString

    assert LineString(candidate.shape.paths[0]).is_simple


def test_invalid_unknown_subject_programs_use_shapespec_scaffold(monkeypatch):
    _clear_custom_shape_cache()
    invalid = json.loads(json.dumps(_program(raised=False)))
    invalid["strokes"][0]["commands"][1]["points"] = []
    geometry = {
        "name": "platypus",
        "variants": [
            {"strategy": "invalid one", "program": invalid},
            {"strategy": "invalid two", "program": invalid},
        ],
        "preferred_variant": 0,
    }
    feature_ids = ("long_body", "wide_bill", "broad_tail", "short_legs")
    verification = {
        "reviews": [{
            "candidate_index": 0,
            "score": 0.8,
            "subject_match": 0.8,
            "silhouette_quality": 0.8,
            "route_readability": 0.8,
            "cue_results": [
                {"feature_id": feature_id, "present": True, "score": 0.8, "reason": "visible"}
                for feature_id in feature_ids
            ],
            "missing_features": [],
            "wrong_relations": [],
            "repair_instructions": [],
        }],
        "recommended_candidate": 0,
    }
    responses = iter([
        LLMResponse(json.dumps(_platypus_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse(json.dumps(verification), "reviewer", "vision-model"),
    ])
    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        lambda *_args, **_kwargs: next(responses),
    )
    state = WorkflowState(
        prompt="a platypus with a wide bill and broad tail in Budapest, about 8 km",
        intent=Intent("a platypus with a wide bill and broad tail", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.source == "llm"
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.8)
    assert passes_ai_shape_quality(state.shape)


def test_invalid_known_subject_programs_use_grounded_candidate_before_text_fallback(monkeypatch):
    _clear_custom_shape_cache()
    invalid = json.loads(json.dumps(_program(raised=False)))
    invalid["strokes"][0]["commands"][1]["points"] = []
    geometry = {
        "name": "waving robot",
        "variants": [
            {"strategy": "invalid one", "program": invalid},
            {"strategy": "invalid two", "program": invalid},
        ],
        "preferred_variant": 0,
    }
    verification = {
        "reviews": [_review(0, 0.82)],
        "recommended_candidate": 0,
    }
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse(json.dumps(verification), "reviewer", "vision-model"),
    ])
    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        lambda *_args, **_kwargs: next(responses),
    )
    state = WorkflowState(
        prompt="a robot waving in Budapest, about 8 km",
        intent=Intent("a robot waving", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.source == "llm"
    assert state.shape.generated_candidate_count == 1
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.82)
    assert not state.errors


def test_known_subject_provider_outage_uses_recognizable_grounded_fallback(monkeypatch):
    _clear_custom_shape_cache()
    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        lambda fallback, **_kwargs: fallback(),
    )
    state = WorkflowState(
        prompt="a robot waving in Budapest, about 8 km",
        intent=Intent("a robot waving", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.source == "fallback"
    assert state.shape.name.startswith("grounded:a robot waving")
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.method == "geometry"
    assert state.shape.feature_paths
    assert "deterministic" in state.errors[0]


def test_compound_provider_outage_prefers_full_semantic_fallback(monkeypatch):
    _clear_custom_shape_cache()
    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        lambda fallback, **_kwargs: fallback(),
    )
    state = WorkflowState(
        prompt="a bicycle carrying a flower basket in Budapest, about 8 km",
        intent=Intent(
            "a bicycle carrying a flower basket",
            None,
            "Budapest",
            "run",
            8,
            None,
        ),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.source == "fallback"
    assert state.shape.name.startswith("grounded:a bicycle")
    assert len(state.shape.paths) == 4
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.method == "geometry"


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
        "reviews": [_review(0, 0.72), _review(1, 0.91), _review(2, 0.60)],
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
    assert state.shape.generated_candidate_count == 3
    assert state.shape.selected_candidate == 1
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.independent is True
    assert state.shape.semantic_verification.provider == "reviewer"
    assert state.shape.semantic_verification.method == "rendered-image-independent"
    assert state.shape.semantic_verification.score == pytest.approx(0.91)
    assert len(calls[2]["images"]) == 3
    assert calls[0]["max_tokens"] == 6144
    assert calls[1]["max_tokens"] == 8192
    assert calls[2]["max_tokens"] == 4096
    assert calls[2]["exclude_provider"] == "generator"
    assert calls[2]["pin_provider"] is False
    assert calls[2]["max_provider_attempts"] == 1


def test_single_provider_uses_disclosed_visual_self_review(monkeypatch):
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
        "reviews": [_review(0, 0.70), _review(1, 0.88), _review(2, 0.60)],
        "recommended_candidate": 1,
    }
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse("{}", "fallback", "geometry-checks"),
        LLMResponse(json.dumps(verification), "generator", "vision-model"),
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
    assert state.shape.selected_candidate == 1
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.88)
    assert state.shape.semantic_verification.provider == "generator"
    assert state.shape.semantic_verification.independent is False
    assert state.shape.semantic_verification.method == "rendered-image-self-review"
    assert calls[2]["exclude_provider"] == "generator"
    assert "exclude_provider" not in calls[3]
    assert calls[3]["max_provider_attempts"] == 1


def test_candidate_selection_prefers_complete_required_cues(monkeypatch):
    _clear_custom_shape_cache()
    geometry = {
        "name": "waving robot",
        "variants": [
            {"strategy": "polished but incomplete", "program": _program(raised=False)},
            {"strategy": "complete silhouette", "program": _program(raised=True)},
        ],
        "preferred_variant": 0,
    }
    verification = {
        "reviews": [
            _review(
                0,
                0.98,
                absent={"raised_arm"},
                missing=["raised_arm"],
            ),
            _review(1, 0.82, wrong_relations=["minor contour proportion note"]),
            _review(2, 0.60),
        ],
        "recommended_candidate": 0,
    }
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse(json.dumps(verification), "reviewer", "vision-model"),
        LLMResponse("{}", "fallback", "none"),
    ])
    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        lambda *_args, **_kwargs: next(responses),
    )
    state = WorkflowState(
        prompt="a robot waving in Budapest, about 8 km",
        intent=Intent("a robot waving", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.selected_candidate == 1
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.missing_features == []
    assert passes_ai_shape_quality(state.shape)


def test_cue_complete_repair_can_win_without_artificial_score_increase(monkeypatch):
    _clear_custom_shape_cache()
    geometry = {
        "name": "waving robot",
        "variants": [
            {"strategy": "compact pose", "program": _program(raised=False)},
            {"strategy": "raised arm silhouette", "program": _program(raised=True)},
        ],
        "preferred_variant": 1,
    }
    initial_review = {
        "reviews": [
            _review(0, 0.60, absent={"raised_arm"}, missing=["raised_arm"]),
            _review(1, 0.74, absent={"raised_arm"}, missing=["raised_arm"]),
            _review(2, 0.50, absent={"raised_arm"}, missing=["raised_arm"]),
        ],
        "recommended_candidate": 1,
    }
    repaired_review = {"reviews": [_review(0, 0.70)], "recommended_candidate": 0}
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse(json.dumps(initial_review), "reviewer", "vision-model"),
        LLMResponse(
            json.dumps({
                "candidate": {
                    "strategy": "cue-complete repair",
                    "program": _program(raised=True),
                }
            }),
            "generator",
            "draw-model",
        ),
        LLMResponse(json.dumps(repaired_review), "reviewer", "vision-model"),
    ])
    monkeypatch.setattr(
        "gps_art_wizzard.agents.shape_agent.try_complete",
        lambda *_args, **_kwargs: next(responses),
    )
    state = WorkflowState(
        prompt="a robot waving in Budapest, about 8 km",
        intent=Intent("a robot waving", None, "Budapest", "run", 8, None),
        plan=Plan(shape_strategy="llm", difficulty="medium"),
    )

    ShapeAgent().run(state)

    assert state.shape is not None
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.70)
    assert state.shape.semantic_verification.missing_features == []
    assert passes_ai_shape_quality(state.shape)


def test_malformed_independent_review_falls_back_to_disclosed_self_review(monkeypatch):
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
        "reviews": [_review(0, 0.69), _review(1, 0.87), _review(2, 0.60)],
        "recommended_candidate": 1,
    }
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse("{}", "reviewer", "broken-review-model"),
        LLMResponse(json.dumps(verification), "generator", "vision-model"),
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
    assert state.shape.selected_candidate == 1
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.87)
    assert state.shape.semantic_verification.independent is False
    assert state.shape.semantic_verification.method == "rendered-image-self-review"
    assert calls[2]["exclude_provider"] == "generator"
    assert "exclude_provider" not in calls[3]


def test_visual_review_maps_filtered_candidate_indices_to_actual_images(monkeypatch):
    _clear_custom_shape_cache()
    invalid = json.loads(json.dumps(_program(raised=False)))
    invalid["strokes"][0]["commands"][1]["points"] = []
    geometry = {
        "name": "waving robot",
        "variants": [
            {"strategy": "compact pose", "program": _program(raised=False)},
            {"strategy": "invalid middle", "program": invalid},
            {"strategy": "raised arm silhouette", "program": _program(raised=True)},
        ],
        "preferred_variant": 2,
    }
    verification = {
        "reviews": [_review(0, 0.70), _review(2, 0.89), _review(1, 0.60)],
        "recommended_candidate": 2,
    }
    responses = iter([
        LLMResponse(json.dumps(_spec_payload()), "generator", "spec-model"),
        LLMResponse(json.dumps(geometry), "generator", "draw-model"),
        LLMResponse("{}", "fallback", "geometry-checks"),
        LLMResponse(json.dumps(verification), "generator", "vision-model"),
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
    assert state.shape.generated_candidate_count == 3
    assert state.shape.selected_candidate == 2
    assert state.shape.semantic_verification is not None
    assert state.shape.semantic_verification.score == pytest.approx(0.89)
    assert len(calls[3]["images"]) == 3
    review_prompt = calls[3]["messages"][0]["content"]
    assert "Image 1 corresponds to candidate_index 0" in review_prompt
    assert "Image 2 corresponds to candidate_index 2" in review_prompt
    assert "Image 3 corresponds to candidate_index 1" in review_prompt


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
        "reviews": [_review(0, 0.5), _review(1, 0.55), _review(2, 0.45)],
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
    assert calls[3]["max_tokens"] == 6144
    assert "typed diagnostics" in calls[3]["messages"][0]["content"]
    assert "second move inside a stroke" in calls[3]["messages"][0]["content"]
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
