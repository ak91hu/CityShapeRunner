import time
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
print("health", c.get("/api/health").json())
print("cities", c.get("/api/cities/search?q=bud").json()["items"][0]["name"])
print("artworks count", len(c.get("/api/artworks?distanceKm=10").json()["items"]))

r = c.post("/api/generation/jobs", json={
    "cityId": "budapest", "activity": "running", "targetDistanceKm": 10,
    "difficulty": "medium", "maxSuggestions": 6,
})
print("create job", r.status_code, r.json())
jid = r.json()["jobId"]
st = {}
for _ in range(30):
    st = c.get(f"/api/generation/jobs/{jid}").json()
    if st["status"] in ("completed", "failed"):
        break
    time.sleep(0.5)
print("final status", st["status"], st.get("progressStage"), "suggestions", len(st.get("suggestions", [])))

if st["status"] == "completed" and st["suggestions"]:
    cand = st["suggestions"][0]
    cid = cand["candidateId"]
    print("top candidate", cand["artworkName"], "fit", cand["fitScore"], "dist", cand["distanceKm"])
    gj = c.get(f"/api/candidates/{cid}/geojson")
    print("geojson", gj.status_code, gj.json()["type"], len(gj.json()["features"]))
    rt = c.post("/api/routes", json={"candidateId": cid})
    print("route", rt.status_code, rt.json()["routeId"], rt.json()["distanceKm"])
    rid = rt.json()["routeId"]
    gpx = c.get(f"/api/routes/{rid}/export/gpx?mode=continuous")
    print("gpx", gpx.status_code, gpx.headers.get("content-disposition"), "chars", len(gpx.text))
    dots = c.get(f"/api/routes/{rid}/export/gpx?mode=connect_the_dots")
    print("dots gpx", dots.status_code, "chars", len(dots.text))
    sh = c.post(f"/api/routes/{rid}/share").json()
    sid = sh["shareId"]
    print("share", sid)
    sv = c.get(f"/api/share/{sid}").json()
    print("share view", sv["cityName"], sv["artworkName"], "features", len(sv["geojson"]["features"]))
else:
    print("JOB FAILED:", st.get("errorCode"), st.get("errorMessage"))
