import time
import pytest
from typing import Any

# Polling timeout helper
def wait_for_job(client, job_id: str, timeout_sec: int = 120) -> dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = client.get(f"/api/generation/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.5)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_sec}s")


def test_generation_success_basic(client):
    """1. Test basic successful generation of a shape in a city."""
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 5.0,
        "difficulty": "medium",
        "artworkIds": ["heart"],
        "maxSuggestions": 3
    }
    resp = client.post("/api/generation/jobs", json=payload)
    assert resp.status_code == 202
    job_id = resp.json()["jobId"]
    
    data = wait_for_job(client, job_id)
    assert data["status"] == "completed"
    assert len(data["suggestions"]) > 0
    
    best = data["suggestions"][0]
    assert best["artworkId"] == "heart"
    assert best["rank"] == 1
    assert best["distanceKm"] > 0


def test_generation_invalid_city(client):
    """2. Test handling of an invalid city."""
    payload = {
        "cityId": "non_existent_city",
        "activity": "running",
        "targetDistanceKm": 5.0,
        "difficulty": "medium",
        "artworkIds": ["heart"]
    }
    resp = client.post("/api/generation/jobs", json=payload)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CITY_NOT_FOUND"


def test_generation_invalid_artwork(client):
    """3. Test handling of an invalid artwork."""
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 5.0,
        "difficulty": "medium",
        "artworkIds": ["invalid_artwork"]
    }
    resp = client.post("/api/generation/jobs", json=payload)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "ARTWORK_NOT_FOUND"


def test_generation_scores_range(client):
    """4. Verify that all returned scores are between 0.0 and 1.0."""
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 4.0,
        "difficulty": "medium",
        "artworkIds": ["star"],
        "maxSuggestions": 2
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    for cand in data["suggestions"]:
        scores = cand["scores"]
        assert 0.0 <= scores["fitScore"] <= 1.0
        assert 0.0 <= scores["shapeSimilarityScore"] <= 1.0
        assert 0.0 <= scores["distanceAccuracyScore"] <= 1.0
        assert 0.0 <= scores["roadQualityScore"] <= 1.0
        assert 0.0 <= scores["continuityScore"] <= 1.0


def test_generation_distance_accuracy(client):
    """5. Verify that the generated routes have a distance roughly close to the target distance."""
    target_dist = 6.0
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": target_dist,
        "difficulty": "medium",
        "artworkIds": ["cat"]
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    best = data["suggestions"][0]
    actual_dist = best["distanceKm"]
    # Allow 40% margin since urban environments are constrained
    assert target_dist * 0.6 <= actual_dist <= target_dist * 1.4


def test_generation_sorting(client):
    """6. Verify that the suggestions are correctly sorted by rank ascending."""
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 5.0,
        "difficulty": "medium",
        "artworkIds": ["circle"],
        "maxSuggestions": 5
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    suggestions = data["suggestions"]
    assert len(suggestions) > 1
    
    ranks = [c["rank"] for c in suggestions]
    assert ranks == sorted(ranks)
    assert ranks[0] == 1
    assert ranks[-1] == len(suggestions)


def test_generation_geojson_endpoint(client):
    """7. Fetch the GeoJSON and verify it is a valid FeatureCollection."""
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 4.0,
        "difficulty": "medium",
        "artworkIds": ["dog"]
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    cand = data["suggestions"][0]
    geojson_url = cand["previewGeoJsonUrl"]
    
    geo_resp = client.get(geojson_url)
    assert geo_resp.status_code == 200
    geo_data = geo_resp.json()
    
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) > 0
    assert geo_data["features"][0]["geometry"]["type"] == "LineString"
    
    coords = geo_data["features"][0]["geometry"]["coordinates"]
    assert len(coords) > 5


def test_generation_target_geojson(client):
    """8. Fetch the target GeoJSON and verify it contains the expected shape features."""
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 5.0,
        "difficulty": "medium",
        "artworkIds": ["heart"]
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    cand = data["suggestions"][0]
    target_url = cand["targetGeoJsonUrl"]
    
    geo_resp = client.get(target_url)
    assert geo_resp.status_code == 200
    geo_data = geo_resp.json()
    
    assert geo_data["type"] == "FeatureCollection"
    # The target should be MultiPolygon, MultiLineString, or Polygon
    geom_type = geo_data["features"][0]["geometry"]["type"]
    assert geom_type in ("Polygon", "MultiPolygon", "LineString", "MultiLineString")


def test_generation_bounding_box(client):
    """9. Ensure all generated coordinates are within the city's bounding box."""
    # Budapest approx bbox: 18.9, 47.3, 19.3, 47.6
    city_resp = client.get("/api/cities/budapest")
    city_data = city_resp.json()
    west, south, east, north = city_data["bbox"]
    
    payload = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 5.0,
        "difficulty": "medium",
        "artworkIds": ["flower"]
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    cand = data["suggestions"][0]
    geo_resp = client.get(cand["previewGeoJsonUrl"])
    geo_data = geo_resp.json()
    
    coords = geo_data["features"][0]["geometry"]["coordinates"]
    for lon, lat in coords:
        assert west <= lon <= east
        assert south <= lat <= north


def test_generation_cycling_activity(client):
    """10. Generate a route for cycling and verify it works without error."""
    payload = {
        "cityId": "budapest",
        "activity": "cycling",
        "targetDistanceKm": 15.0,
        "difficulty": "medium",
        "artworkIds": ["bicycle"],
        "maxSuggestions": 1
    }
    resp = client.post("/api/generation/jobs", json=payload)
    data = wait_for_job(client, resp.json()["jobId"])
    assert data["status"] == "completed"
    
    cand = data["suggestions"][0]
    assert cand["distanceKm"] > 5.0
    
    geo_resp = client.get(cand["previewGeoJsonUrl"])
    assert geo_resp.status_code == 200
