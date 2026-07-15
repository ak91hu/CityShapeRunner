from __future__ import annotations


def test_search_returns_budapest(client):
    r = client.get("/api/cities/search", params={"q": "Budapest"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == "budapest" for i in items)
    
    budapest_item = next(i for i in items if i["id"] == "budapest")
    assert round(budapest_item["centroid"]["lat"], 4) == 47.4979


def test_search_min_length_returns_validation_error(client):
    r = client.get("/api/cities/search", params={"q": "B"})
    assert r.status_code == 422  # spec: minimum 2 characters
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_city_by_id(client):
    r = client.get("/api/cities/budapest")
    assert r.status_code == 200
    assert r.json()["name"] == "Budapest"
    assert isinstance(r.json().get("featuredArtworkIds"), list)


def test_get_city_not_found(client):
    r = client.get("/api/cities/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CITY_NOT_FOUND"
