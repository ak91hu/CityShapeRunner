from __future__ import annotations

import math


from app.core import geometry as geom


def test_parse_svg_path_returns_polylines():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M10 10 L 90 10 L 50 90 Z"/></svg>'
    pls = geom.parse_svg(svg)
    assert len(pls) == 1
    assert pls[0].closed is True
    assert len(pls[0].points) >= 3


def test_parse_svg_basic_primitives():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<circle cx="50" cy="50" r="20"/>'
        '<rect x="10" y="10" width="20" height="30"/>'
        '<polyline points="0,0 50,50 100,0"/>'
        '<line x1="0" y1="0" x2="100" y2="100"/>'
        "</svg>"
    )
    pls = geom.parse_svg(svg)
    assert len(pls) == 4  # circle, rect, polyline, line


def test_parse_svg_bezier_sampling():
    # heart uses cubic beziers
    from app.core.seed import get_artwork
    heart = get_artwork("heart")
    assert heart.normalized_length > 0
    assert len(heart.normalized) >= 1
    # bezier sampling should yield many points, not just the 4 control points
    assert len(heart.normalized[0].points) > 20


def test_normalize_preserves_aspect_ratio():
    pls = [geom.Polyline(points=[(0, 0), (200, 0), (200, 100), (0, 100)], closed=True)]
    norm = geom.normalize_polylines(pls)
    minx, miny, maxx, maxy = geom.polylines_bbox(norm)
    w = maxx - minx
    h = maxy - miny
    assert math.isclose(w, 1.0, abs_tol=1e-9)
    assert math.isclose(h, 0.5, abs_tol=1e-9)  # 100/200


def test_transform_scale_rotation_translation(projector):
    normalized = [geom.Polyline(points=[(0.0, 0.0), (1.0, 0.0)], closed=False)]
    anchor = (47.5, 19.04)

    placed = geom.transform_polyline(normalized, anchor, 1000.0, 0.0, projector)
    a = projector.to_metric(placed[0].points[0][1], placed[0].points[0][0])
    b = projector.to_metric(placed[0].points[1][1], placed[0].points[1][0])
    # first point == anchor (origin of normalized bbox)
    assert math.isclose(a[0], 0.0, abs_tol=1e-3)
    assert math.isclose(a[1], 0.0, abs_tol=1e-3)
    # segment of length 1 * 1000m -> 1000m
    assert math.isclose(math.hypot(b[0] - a[0], b[1] - a[1]), 1000.0, rel_tol=1e-3)

    # 90-degree rotation maps (1,0) -> (0,1) in y-up metric
    rot = geom.transform_polyline(normalized, anchor, 1000.0, 90.0, projector)
    rb = projector.to_metric(rot[0].points[1][1], rot[0].points[1][0])
    assert math.isclose(rb[0], 0.0, abs_tol=1e-3)
    assert math.isclose(rb[1], 1000.0, rel_tol=1e-3)


def test_estimate_scale_candidates():
    cands = geom.estimate_scale_candidates(2.5, 10000.0, 1.2)
    assert len(cands) == 5
    base = 10000.0 / (2.5 * 1.2)
    assert math.isclose(cands[2], base, rel_tol=1e-9)
    assert cands == sorted(cands)


def test_rotation_candidates_symmetric_reduced():
    assert len(geom.rotation_candidates(True)) < len(geom.rotation_candidates(False))
    assert 0.0 in geom.rotation_candidates(True)


def test_shape_similarity_identical_is_high():
    pts = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
    s = geom.shape_similarity(pts, pts, 1000.0)
    assert s > 0.95


def test_shape_similarity_high_beats_poor():
    target = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
    good = list(target)
    poor = [(0, 0), (100, 50), (50, 100), (0, 0)]
    s_good = geom.shape_similarity(target, good, 1000.0)
    s_poor = geom.shape_similarity(target, poor, 1000.0)
    assert s_good > s_poor


def test_resample_polyline_count():
    pts = [(0, 0), (10, 0), (10, 10)]
    out = geom.resample_polyline(pts, 50)
    assert len(out) == 50

def test_higher_resolution_sampling():
    from app.core.geometry import _sample_cubic, _sample_quadratic, resample_polyline
    # Verify that the defaults provide the massive 48 / 40 point counts requested
    assert len(_sample_cubic((0,0), (1,1), (2,2), (3,3))) == 49
    assert len(_sample_quadratic((0,0), (1,1), (2,2))) == 41
    # Check default upscaling
    pts = [(0, 0), (10, 0), (10, 10)]
    out = resample_polyline(pts)
    assert len(out) == 512
