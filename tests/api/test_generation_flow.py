from __future__ import annotations

import time


def _wait(client, job_id, timeout=40):
    st = {}
    for _ in range(timeout * 2):
        st = client.get(f"/api/generation/jobs/{job_id}").json()
        if st["status"] in ("completed", "failed", "cancelled"):
            return st
        time.sleep(0.5)
    return st


def _create_budapest_heart(client, **overrides):
    body = {
        "cityId": "budapest",
        "activity": "running",
        "targetDistanceKm": 10,
        "difficulty": "medium",
        "maxSuggestions": 6,
    }
    body.update(overrides)
    return client.post("/api/generation/jobs", json=body)


def test_full_generation_flow(client):
    r = _create_budapest_heart(client)
    assert r.status_code == 202
    job_id = r.json()["jobId"]
    st = _wait(client, job_id)
    assert st["status"] == "completed", st
    assert len(st["suggestions"]) >= 1
    top = st["suggestions"][0]
    assert top["rank"] == 1
    assert top["fitScore"] >= 0.0
    assert top["previewGeoJsonUrl"].endswith("/geojson")

    # candidate geojson
    gj = client.get(f"/api/candidates/{top['candidateId']}/geojson")
    assert gj.status_code == 200
    fc = gj.json()
    assert fc["type"] == "FeatureCollection"
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert "route" in kinds and "target_artwork" in kinds

    # target-only layer
    gj_t = client.get(f"/api/candidates/{top['candidateId']}/geojson?layer=target")
    kinds_t = {f["properties"]["kind"] for f in gj_t.json()["features"]}
    assert kinds_t == {"target_artwork"}

    # create route
    rt = client.post("/api/routes", json={"candidateId": top["candidateId"]})
    assert rt.status_code == 201
    route = rt.json()
    rid = route["routeId"]
    assert route["gpxUrl"].endswith("mode=continuous")
    assert route["gpxConnectTheDotsUrl"].endswith("mode=connect_the_dots")

    # GPX continuous export
    gpx = client.get(f"/api/routes/{rid}/export/gpx", params={"mode": "continuous"})
    assert gpx.status_code == 200
    assert gpx.headers["content-type"] == "application/gpx+xml"
    assert "attachment" in gpx.headers["content-disposition"]
    assert gpx.text.startswith("<?xml")
    assert "<gpx" in gpx.text
    assert "budapest-heart" in gpx.headers["content-disposition"]
    assert "running.gpx" in gpx.headers["content-disposition"]

    # GPX connect-the-dots
    dots = client.get(f"/api/routes/{rid}/export/gpx", params={"mode": "connect_the_dots"})
    assert dots.status_code == 200
    assert "dots" in dots.headers["content-disposition"]
    # continuous should have at least as many trkpt as dots
    assert gpx.text.count("<trkpt") >= dots.text.count("<trkpt")

    # share
    sh = client.post(f"/api/routes/{rid}/share")
    assert sh.status_code == 200
    sid = sh.json()["shareId"]
    sv = client.get(f"/api/share/{sid}")
    assert sv.status_code == 200
    assert sv.json()["cityName"] == "Budapest"
    assert sv.json()["artworkName"] == "Heart"
    assert sv.json()["geojson"]["type"] == "FeatureCollection"


def test_idempotent_request_returns_same_job(client):
    r1 = _create_budapest_heart(client)
    j1 = r1.json()["jobId"]
    _wait(client, j1)
    r2 = _create_budapest_heart(client)
    assert r2.json()["jobId"] == j1


def test_force_creates_new_job(client):
    r1 = _create_budapest_heart(client)
    j1 = r1.json()["jobId"]
    _wait(client, j1)
    r2 = _create_budapest_heart(client, force=True)
    assert r2.json()["jobId"] != j1


def test_validation_bad_activity(client):
    r = client.post("/api/generation/jobs", json={
        "cityId": "budapest", "activity": "flying", "targetDistanceKm": 10, "difficulty": "medium",
    })
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "activity" in (body["error"].get("fields") or {})


def test_validation_distance_out_of_range(client):
    r = client.post("/api/generation/jobs", json={
        "cityId": "budapest", "activity": "running", "targetDistanceKm": 2, "difficulty": "medium",
    })
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_city_returns_error(client):
    r = client.post("/api/generation/jobs", json={
        "cityId": "atlantis", "activity": "running", "targetDistanceKm": 10, "difficulty": "medium",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "CITY_NOT_FOUND"


def test_cancel_job(client):
    r = _create_budapest_heart(client)
    jid = r.json()["jobId"]
    c = client.post(f"/api/generation/jobs/{jid}/cancel")
    assert c.status_code == 200
    # status should be cancelled or completed (race); accept cancelled
    assert c.json()["status"] in ("cancelled", "completed")


def test_job_not_found(client):
    r = client.get("/api/generation/jobs/job_doesnotexist")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_gpx_invalid_mode(client):
    r = _create_budapest_heart(client)
    jid = r.json()["jobId"]
    st = _wait(client, jid)
    cid = st["suggestions"][0]["candidateId"]
    rid = client.post("/api/routes", json={"candidateId": cid}).json()["routeId"]
    bad = client.get(f"/api/routes/{rid}/export/gpx", params={"mode": "kml"})
    assert bad.status_code == 422


def test_route_not_found(client):
    r = client.get("/api/routes/route_none/export/gpx", params={"mode": "continuous"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "ROUTE_NOT_FOUND"
