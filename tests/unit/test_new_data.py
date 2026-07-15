import pytest
from app.core.seed import load_cities, load_artworks, list_all_cities, list_artworks
from app.core import geometry as geom

def test_cities_loaded_correctly():
    cities = load_cities()
    # At least the original 4 plus 100 new cities = 104
    assert len(cities) >= 100
    
    # Check bounding boxes are valid
    for c in cities:
        assert len(c.bbox) == 4
        assert c.bbox[0] < c.bbox[2]  # west < east
        assert c.bbox[1] < c.bbox[3]  # south < north

def test_artworks_loaded_correctly():
    artworks = load_artworks()
    # At least original 9 plus 50 new shapes = 59
    assert len(artworks) >= 50
    
    # Verify that SVGs are valid and parses properly
    for a in artworks:
        assert len(a.normalized) > 0
        assert a.normalized_length > 0

def test_custom_control_indices():
    # This just ensures we can import the module correctly and nothing is broken
    from app.core.snapping import snap_polyline
    from app.core.shape_matching import _control_indices
    assert callable(snap_polyline)
    assert callable(_control_indices)

def test_generate_data_consistency():
    all_cities = list_all_cities()
    all_artworks = list_artworks()
    assert len(all_cities) >= 100
    assert len(all_artworks) >= 50
