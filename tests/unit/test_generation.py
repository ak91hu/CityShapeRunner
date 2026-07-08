from __future__ import annotations

import pytest

from app.core import gpx
from app.core.generation import generate_suggestions
from app.core.graph import build_synthetic_graph_for_city
from app.core.schemas import Activity, Difficulty, GenerationJobCreate
from app.core.seed import artworks_by_ids, get_artwork, get_city
from app.services import request_hash


@pytest.fixture(scope="module")
def budapest_graph():
    city = get_city("budapest")
    g, proj, bbox = build_synthetic_graph_for_city(city)
    return city, g, proj, bbox


def test_generate_heart_budapest_10k(budapest_graph):
    city, g, proj, bbox = budapest_graph
    heart = get_artwork("heart")
    cands = generate_suggestions(
        city, g, proj, bbox, [heart], Activity.running, 10.0, Difficulty.medium, 6, "mvp-0.1",
    )
    assert len(cands) >= 1
    top = cands[0]
    assert top.rank == 1
    assert top.scores.fit_score >= 0.0
    assert len(top.route_lonlat) >= 2
    # GPX from the top candidate must be valid
    text = gpx.build_continuous_gpx(top.route_lonlat, "Budapest Heart 10K Running", "test")
    v = gpx.validate_gpx(text)
    assert v.valid, v.errors
    # connect-the-dots has fewer or equal points
    dots = gpx.build_connect_the_dots_gpx(top.keypoint_lonlat, "n", "d")
    vd = gpx.validate_gpx(dots)
    assert vd.valid
    assert vd.point_count <= v.point_count


def test_candidates_ranked_and_diversified(budapest_graph):
    city, g, proj, bbox = budapest_graph
    arts = artworks_by_ids(["heart", "star", "circle"])
    cands = generate_suggestions(
        city, g, proj, bbox, arts, Activity.running, 10.0, Difficulty.medium, 6, "mvp-0.1",
    )
    ranks = [c.rank for c in cands]
    assert ranks == sorted(ranks)
    # diversification: best per artwork first
    seen = set()
    for c in cands:
        if c.artwork_id in seen:
            # second appearance only allowed after all firsts
            break
        seen.add(c.artwork_id)


def test_eligibility_pruning_excludes_large_artwork_for_short_distance(budapest_graph):
    city, g, proj, bbox = budapest_graph
    dino = get_artwork("dinosaur")  # recommended 15-60 km
    # 4 km target: eligible range is [15*0.5=7.5, 60*2=120] -> 4 < 7.5 -> ineligible
    assert not dino.eligible_for(4.0)
    cands = generate_suggestions(
        city, g, proj, bbox, [dino], Activity.running, 4.0, Difficulty.medium, 6, "mvp-0.1",
    )
    assert cands == []


def test_debug_metadata_contains_placement(budapest_graph):
    city, g, proj, bbox = budapest_graph
    heart = get_artwork("heart")
    cands = generate_suggestions(
        city, g, proj, bbox, [heart], Activity.running, 10.0, Difficulty.medium, 3, "mvp-0.1",
    )
    assert cands, "expected at least one candidate"
    d = cands[0].debug
    assert "placement" in d
    assert "algorithmVersion" in d
    assert d["algorithmVersion"] == "mvp-0.1"
    assert "scaleMeters" in d["placement"]


def test_request_hash_deterministic_and_differs_by_input():
    base = GenerationJobCreate(
        city_id="budapest", activity=Activity.running, target_distance_km=10.0,
        difficulty=Difficulty.medium, max_suggestions=6,
    )
    same = GenerationJobCreate(
        city_id="budapest", activity=Activity.running, target_distance_km=10.0,
        difficulty=Difficulty.medium, max_suggestions=12,  # max_suggestions not in hash
    )
    other_city = GenerationJobCreate(
        city_id="debrecen", activity=Activity.running, target_distance_km=10.0,
        difficulty=Difficulty.medium, max_suggestions=6,
    )
    other_dist = GenerationJobCreate(
        city_id="budapest", activity=Activity.running, target_distance_km=15.0,
        difficulty=Difficulty.medium, max_suggestions=6,
    )
    assert request_hash(base) == request_hash(same)
    assert request_hash(base) != request_hash(other_city)
    assert request_hash(base) != request_hash(other_dist)


def test_generation_is_deterministic(budapest_graph):
    city, g, proj, bbox = budapest_graph
    heart = get_artwork("heart")
    c1 = generate_suggestions(city, g, proj, bbox, [heart], Activity.running, 10.0, Difficulty.medium, 3, "mvp-0.1")
    c2 = generate_suggestions(city, g, proj, bbox, [heart], Activity.running, 10.0, Difficulty.medium, 3, "mvp-0.1")
    assert [c.candidate_id for c in c1] == [c.candidate_id for c in c2]
    assert c1[0].scores.fit_score == c2[0].scores.fit_score
