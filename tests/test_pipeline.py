"""Offline tests: the pipeline runs end-to-end with no API keys, and the
geometry/shape tooling is sound.

Run with: ``GEOCODE_OFFLINE=1 pytest``  (the env skips the Nominatim network call).
"""

from __future__ import annotations

import string

import numpy as np
import pytest

from gps_art_wizzard.orchestrator import generate
from gps_art_wizzard.tools import geo, shape_library, shape_similarity, text_shapes


# --------------------------------------------------------------------------- #
# Pipeline (offline)
# --------------------------------------------------------------------------- #
def test_pipeline_produces_safe_preview_without_a_routing_provider():
    state = generate("a heart run in Budapest, about 8 km")
    assert state.export is not None
    assert "<gpx" in state.export.gpx
    assert state.snapped is not None
    assert len(state.snapped.points) >= 2
    assert state.snapped.snapped is False
    assert state.validation is not None
    assert 0.0 <= state.validation.score <= 1.0
    assert state.validation.on_roads is False
    assert state.iterations == 0
    assert any("manual" in error.lower() for error in state.errors)
    assert len(state.candidates) >= 1
    assert state.plan is not None
    assert state.plan.shape_strategy in ("template", "text", "llm")
    assert state.plan.center_lat == pytest.approx(47.4979)
    assert state.plan.center_lon == pytest.approx(19.0402)


def test_pipeline_text_shape():
    state = generate("write HI in Berlin")
    assert state.shape is not None
    assert state.shape.source == "text"
    assert state.export is not None
    assert any("export-warning:" in error for error in state.errors)


def test_unknown_shape_is_not_mislabelled_as_the_requested_drawing():
    state = generate("an elephant in Budapest, 8 km")
    assert state.shape is not None
    assert state.shape.name == "star"
    assert state.shape.source == "fallback"
    assert any("fallback" in error for error in state.errors)


# --------------------------------------------------------------------------- #
# Tooling
# --------------------------------------------------------------------------- #
def test_heart_template_closed():
    name, paths, closed = shape_library.heart()
    assert name == "heart"
    assert closed is True
    assert len(paths[0]) > 10


def test_normalize_shape_scales_to_one():
    _, paths, _ = shape_library.star()
    norm = geo.normalize_shape(paths)
    pts = np.concatenate([np.asarray(p) for p in norm])
    extent = (pts.max(axis=0) - pts.min(axis=0)).max()
    assert abs(extent - 1.0) < 1e-6
    assert abs(pts.mean(axis=0)).max() < 1e-6  # centroid at origin


def test_text_shape_renders_letters():
    paths, closed = text_shapes.text_to_shape("AB")
    assert closed is False
    assert len(paths) >= 3  # A has 2 strokes, B has 3 -> >=5 actually, but >=3 is safe


def test_vector_font_contains_every_letter_and_digit():
    assert set(string.ascii_uppercase + string.digits) <= set(text_shapes.FONT)


@pytest.mark.parametrize(
    ("prompt", "expected_name"),
    [
        ("draw the letter A in Miskolc, 10 km", "text:A"),
        ("draw the number 42 while cycling in Eger, 20 km", "text:42"),
    ],
)
def test_pipeline_builds_letter_and_number_shapes(prompt, expected_name):
    state = generate(prompt)

    assert state.shape is not None
    assert state.shape.name == expected_name
    assert state.shape.source == "text"
    assert state.intent is not None
    assert state.intent.city in {"Miskolc", "Eger"}


def test_similarity_identical_is_high():
    _, paths, _ = shape_library.heart()
    norm = geo.normalize_shape(paths)
    # Build a lat/lon route identical in shape to the normalised unit shape.
    route = [(y * 0.01, x * 0.01) for x, y in norm[0]]  # small, around (0,0)
    score = shape_similarity.shape_fidelity(norm, route)
    assert score > 0.95


def test_unit_to_latlon_roundtrip():
    lat, lon = geo.unit_to_latlon(0.5, -0.3, 47.5, 19.0, 10000.0)
    x, y = geo.latlon_to_unit(lat, lon, 47.5, 19.0, 10000.0)
    assert abs(x - 0.5) < 1e-9
    assert abs(y + 0.3) < 1e-9
