import importlib.util
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_generation_services.py"
SPEC = importlib.util.spec_from_file_location("check_generation_services", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
check_generation_services = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_generation_services)


def test_ors_probe_uses_heigit_directions_and_configured_key(monkeypatch):
    request = {}

    def fake_post(url, **kwargs):
        request.update(url=url, **kwargs)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(check_generation_services.httpx, "post", fake_post)
    cfg = SimpleNamespace(
        ors_base_url="https://api.heigit.org/openrouteservice",
        ors_api_key="secret-test-key",
    )

    result = check_generation_services._probe_ors(cfg)

    assert request["url"] == (
        "https://api.heigit.org/openrouteservice/"
        "v2/directions/foot-walking/geojson"
    )
    assert request["headers"]["Authorization"] == "secret-test-key"
    assert request["json"]["coordinates"] == [
        [19.0402, 47.4979],
        [19.0440, 47.4988],
    ]
    assert result == {
        "service": "ors",
        "http_status": 200,
        "available": True,
        "api_key_configured": True,
    }
