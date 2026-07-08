from __future__ import annotations

from app.core.seed import get_artwork, get_city, list_artworks, search_cities, load_artworks, load_cities


def test_seed_city_counts():
    cities = load_cities()
    assert len(cities) >= 10  # spec: at least 10 Hungarian cities
    names = {c.name for c in cities}
    assert "Budapest" in names
    assert "Gyöngyös" in names


def test_seed_artwork_counts():
    arts = load_artworks()
    assert len(arts) >= 20  # spec: at least 20 shapes
    ids = {a.id for a in arts}
    for required in ["heart", "star", "bridge", "danube-wave", "crown", "bicycle"]:
        assert required in ids


def test_all_artwork_svgs_parse():
    for a in load_artworks():
        assert a.normalized_length > 0, f"{a.id} has zero normalized length"
        assert len(a.normalized) >= 1
        assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for pl in a.normalized for x, y in pl.points), a.id


def test_search_budapest():
    res = search_cities("Budapest")
    assert any(c.id == "budapest" for c in res)


def test_search_min_chars():
    assert search_cities("B") == []


def test_search_country_filter():
    res = search_cities("Budapest", country="HU")
    assert all(c.country_code == "HU" for c in res)
    assert search_cities("Budapest", country="DE") == []


def test_artwork_eligibility():
    heart = get_artwork("heart")  # 5-15 km
    assert heart.eligible_for(10.0)
    assert heart.eligible_for(7.5)   # 5*0.5
    assert heart.eligible_for(30.0)  # 15*2
    assert not heart.eligible_for(2.0)
    assert not heart.eligible_for(40.0)


def test_list_artworks_distance_filter():
    all_arts = list_artworks()
    filtered = list_artworks(distance_km=10.0)
    assert len(filtered) <= len(all_arts)
    assert all(a.recommended_min_km * 0.5 <= 10.0 <= a.recommended_max_km * 2.0 for a in filtered)


def test_city_detail_signature_artworks():
    bp = get_city("budapest")
    assert "heart" in bp.signature_artwork_ids
    assert "parliament" in bp.signature_artwork_ids
