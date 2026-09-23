"""Static SPA cache policy regression tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gps_art_wizzard.main import CachedSPAStaticFiles


def test_fingerprinted_assets_are_immutable_but_html_is_revalidated(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "assets" / "index-AbCdEf12.js").write_text("export {};", encoding="utf-8")
    (tmp_path / "budapest-heart-route-4bdf5a785149.webp").write_bytes(b"webp")

    app = FastAPI()
    app.mount("/", CachedSPAStaticFiles(directory=tmp_path, html=True))
    with TestClient(app) as client:
        page = client.get("/")
        bundle = client.get("/assets/index-AbCdEf12.js")
        image = client.get("/budapest-heart-route-4bdf5a785149.webp")
        missing = client.get("/missing")

    assert page.headers["Cache-Control"] == "no-cache"
    assert bundle.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert image.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert missing.status_code == 404
    assert "Cache-Control" not in missing.headers
