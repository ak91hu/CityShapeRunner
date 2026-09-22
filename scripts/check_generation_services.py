"""Read-only endpoint connectivity probes. Never print keys or response bodies.

ORS does not expose a public health endpoint.  Probe its actual directions API
with two nearby coordinates instead, so the result also verifies the configured
API key after the migration to ``api.heigit.org``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gps_art_wizzard.config import get_settings  # noqa: E402


def _probe_ors(cfg) -> dict[str, object]:
    url = f"{cfg.ors_base_url.rstrip('/')}/v2/directions/foot-walking/geojson"
    headers = {"Content-Type": "application/json"}
    if cfg.ors_api_key:
        headers["Authorization"] = cfg.ors_api_key
    response = httpx.post(
        url,
        headers=headers,
        json={
            # A short, routable segment in central Budapest.  This spends one
            # minimal directions request but validates DNS, TLS, key and API.
            "coordinates": [[19.0402, 47.4979], [19.0440, 47.4988]],
        },
        timeout=10,
    )
    return {
        "service": "ors",
        "http_status": response.status_code,
        "available": response.status_code == 200,
        "api_key_configured": bool(cfg.ors_api_key),
    }


def main() -> None:
    cfg = get_settings()
    results = []
    try:
        response = httpx.get(cfg.llm.opencode_base_url + "/models", timeout=5)
        results.append({
            "service": "opencode",
            "http_status": response.status_code,
            "available": response.status_code == 200,
        })
    except httpx.HTTPError as error:
        results.append({
            "service": "opencode",
            "available": False,
            "error_type": type(error).__name__,
        })
    try:
        results.append(_probe_ors(cfg.routing))
    except httpx.HTTPError as error:
        results.append({
            "service": "ors",
            "available": False,
            "api_key_configured": bool(cfg.routing.ors_api_key),
            "error_type": type(error).__name__,
        })
    print(json.dumps(results))


if __name__ == "__main__":
    main()
