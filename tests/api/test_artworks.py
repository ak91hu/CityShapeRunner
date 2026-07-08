from __future__ import annotations


def test_list_artworks(client):
    r = client.get("/api/artworks")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 20
    heart = next(i for i in items if i["id"] == "heart")
    assert heart["previewSvgUrl"].endswith("heart.svg")


def test_list_artworks_distance_filter(client):
    r = client.get("/api/artworks", params={"distanceKm": 10})
    assert r.status_code == 200
    # dinosaur (15-60km) is eligible at 10km? min*0.5=7.5 <= 10 -> eligible
    # but a 3km query should exclude dinosaur
    r3 = client.get("/api/artworks", params={"distanceKm": 3})
    items3 = r3.json()["items"]
    assert all(i["id"] != "dinosaur" for i in items3)


def test_get_artwork(client):
    r = client.get("/api/artworks/heart")
    assert r.status_code == 200
    assert r.json()["name"] == "Heart"
    assert r.json()["normalizedLength"] > 0


def test_get_artwork_not_found(client):
    r = client.get("/api/artworks/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ARTWORK_NOT_FOUND"
