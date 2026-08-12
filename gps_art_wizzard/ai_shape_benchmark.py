"""Stable benchmark prompts and result summaries for free-text AI drawing."""

from __future__ import annotations

from dataclasses import dataclass

from .state import Shape


@dataclass(frozen=True)
class AIShapeBenchmarkCase:
    id: str
    prompt: str
    category: str
    language: str = "en"


AI_SHAPE_BENCHMARK_CASES = (
    AIShapeBenchmarkCase("simple_robot", "a friendly walking robot", "object"),
    AIShapeBenchmarkCase("robot_pose", "a robot waving with its left arm", "pose"),
    AIShapeBenchmarkCase("animal_parts", "a platypus with a wide bill and broad tail", "animal"),
    AIShapeBenchmarkCase("animal_action", "a fox jumping over a crescent moon", "relationship"),
    AIShapeBenchmarkCase("held_object", "a robot holding an open umbrella", "relationship"),
    AIShapeBenchmarkCase("vehicle_modifier", "a small sailboat with two full sails", "vehicle"),
    AIShapeBenchmarkCase("rare_object", "an antique astrolabe with a hanging ring", "rare"),
    AIShapeBenchmarkCase("fantasy", "a seated dragon wearing a three-point crown", "fantasy"),
    AIShapeBenchmarkCase("architecture", "a lighthouse above two crashing waves", "scene"),
    AIShapeBenchmarkCase("food", "a steaming coffee cup with a large handle", "object"),
    AIShapeBenchmarkCase("hu_robot", "egy integető robot antennával", "multilingual", "hu"),
    AIShapeBenchmarkCase("hu_animal", "egy koronás sárkány összecsukott szárnyakkal", "multilingual", "hu"),
    AIShapeBenchmarkCase("hu_scene", "világítótorony két nagy hullám felett", "multilingual", "hu"),
    AIShapeBenchmarkCase("de_object", "ein sitzender Teddybär mit großem Hut", "multilingual", "de"),
    AIShapeBenchmarkCase("fr_pose", "un chat qui regarde par-dessus son épaule", "multilingual", "fr"),
    AIShapeBenchmarkCase("negative_space", "a bold key with a large round bow and one tooth", "negative-space"),
    AIShapeBenchmarkCase("asymmetric", "a runner leaning forward with one knee raised", "pose"),
    AIShapeBenchmarkCase("compound", "a bicycle carrying a flower basket", "compound"),
    AIShapeBenchmarkCase("abstract", "a spiral galaxy with two broad arms", "abstract"),
    AIShapeBenchmarkCase("ambiguous", "a phoenix rising from three flames", "ambiguous"),
)


def benchmark_shape_record(case: AIShapeBenchmarkCase, shape: Shape) -> dict[str, object]:
    """Create a JSON-ready record without claiming a visual score when none exists."""

    review = shape.semantic_verification
    return {
        "id": case.id,
        "prompt": case.prompt,
        "category": case.category,
        "language": case.language,
        "shape_name": shape.name,
        "source": shape.source,
        "candidate_count": shape.generated_candidate_count,
        "selected_candidate": shape.selected_candidate,
        "spec_feature_count": len(shape.spec.recognition_features) if shape.spec else 0,
        "semantic_score": review.score if review else None,
        "independent_verifier": bool(review and review.independent),
        "missing_features": list(review.missing_features) if review else [],
        "wrong_relations": list(review.wrong_relations) if review else [],
        "path_count": len(shape.paths),
        "point_count": sum(len(path) for path in shape.paths),
    }

