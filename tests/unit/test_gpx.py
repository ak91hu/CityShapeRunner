from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.core.gpx import (
    build_continuous_gpx,
    file_name,
    validate_gpx,
)

POINTS = [(47.4979, 19.0402), (47.4981, 19.0410), (47.4985, 19.0420)]


def test_continuous_gpx_valid_xml():
    text = build_continuous_gpx(POINTS, "Test Route", "desc")
    v = validate_gpx(text)
    assert v.valid, v.errors
    assert v.point_count == 3
    root = ET.fromstring(text)
    assert root.get("version") == "1.1"
    assert root.tag.endswith("gpx")


def test_validate_rejects_bad_coords():
    bad = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>' \
          '<trkpt lat="999" lon="19.0"></trkpt><trkpt lat="47.5" lon="19.0"></trkpt></trkseg></trk></gpx>'
    v = validate_gpx(bad)
    assert not v.valid
    assert "trkpt_coord_out_of_range" in v.errors


def test_validate_rejects_non_xml():
    v = validate_gpx("not xml")
    assert not v.valid


def test_validate_rejects_too_few_points():
    one = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>' \
          '<trkpt lat="47.5" lon="19.0"></trkpt></trkseg></trk></gpx>'
    v = validate_gpx(one)
    assert not v.valid
    assert "insufficient_trackpoints" in v.errors


def test_file_naming():
    name = file_name("Budapest", "Heart", 10.18, "running")
    assert name == "budapest-heart-10k-running.gpx"
    name_dots = file_name("Budapest", "Heart", 10.18, "running", "connect_the_dots")
    assert name_dots == "budapest-heart-10k-running-dots.gpx"


def test_gpx_no_duplicate_consecutive_points():
    pts = [(47.5, 19.0), (47.5, 19.0), (47.51, 19.01)]
    text = build_continuous_gpx(pts, "n", "d")
    v = validate_gpx(text)
    assert v.valid
    assert v.point_count == 2  # duplicate removed


def test_gpx_requires_two_points():
    with pytest.raises(ValueError):
        build_continuous_gpx([(47.5, 19.0)], "n", "d")
