# GPS Art Wizard

[![CI](https://github.com/ak91hu/CityShapeRunner/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ak91hu/CityShapeRunner/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-5FA04E?logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.140-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![Northflank ready](https://img.shields.io/badge/Northflank-ready-6C5CE7)](docs/deployment.md#northflank-developer-sandbox)
[![Grafana Cloud Logs](https://img.shields.io/badge/Grafana_Cloud-logs-F46800?logo=grafana&logoColor=white)](docs/deployment.md#persistent-and-searchable-grafana-cloud-logs)

Turn a run or ride into a drawing. Describe an idea—or choose one of 32 quick
starts—and GPS Art Wizard tests the outline against real streets, compares
nearby placements and orientations, and shows how recognisable the resulting
route is before enabling a download.

The project combines 33 deterministic shape templates, a complete A–Z/0–9
vector font, curated Hungarian city profiles, optional LLM planning,
OpenRouteService street routing, quantitative shape validation, and guarded
GPX/TCX export. Every fully routed result is retained as a selectable candidate.
Quality thresholds rank and warn instead of deleting a route, so lower-scoring
results remain available for comparison, manual correction, and export.

Route search is coarse-to-fine. Before spending Directions requests, one
batched road-snap preflight compares up to 180 city-wide
translation/rotation/scale placements. A quality-and-diversity selector sends
seven genuinely different alternatives to the full router, while every
preflight score remains in the diagnostics. Eighteen curvature-preserving
guide points per placement improve the proxy without adding Directions calls.

Recognition is evaluated from outline coverage, characteristic turns,
street-detour stretch, and preserved proportions—not only average point
distance. The map overlays the intended dashed contour on the routed line. If
an explicitly requested drawing misses a recommended target, the planner
measures simpler city-aware templates and recommends the strongest result
without removing the original.

## Research basis

The pipeline is an engineering adaptation of published GPS-art, computational
geometry, route-choice, and map-matching research. It does not claim to
reproduce every paper's custom graph algorithm; instead, it maps the findings
to operations available through the hosted OpenRouteService API.

| Research finding | Consequence in GPS Art Wizard |
|---|---|
| Ordinary waypoint routers can turn off-network drawing points into large detours or visually destructive turns; GPS art benefits from a shape-aware graph cost ([Waschk & Krüger, 2019](https://doi.org/10.1007/s41095-019-0146-z)). | Placements are screened before Directions routing, curvature-bearing guide points are preserved, and the complete returned street polyline is measured against the intended outline. |
| Template placement, graph search, candidate comparison, and interactive adjustment are complementary stages rather than one routing call ([Powałka, 2023](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad)). | A city-wide transform search produces several routed alternatives, while the browser editor lets the user correct control points and request a fresh route. |
| Turning functions compare polygonal shape in a way that can be normalised for translation, rotation, and scale ([Arkin et al., 1991](https://doi.org/10.1109/34.75509)). | Characteristic turns and their order contribute to recognition; mean point distance is never the sole likeness measure. |
| Turning angles, approximate road polylines, and internal length ratios help retrieve recognisable graphics and reject stretched lookalikes in road networks ([Li & Fu, 2026](https://doi.org/10.3390/ijgi15030098)). | Preflight and final validation score angular relations, extent, segment proportions, coverage, and collapse instead of accepting nearest-road distance alone. |
| Useful alternative sets must control overlap, or a top-*k* list can contain near-duplicates ([Nassir et al., 2014](https://doi.org/10.3141/2430-18)). | The seven expensive routing slots balance proxy quality with separation in position, rotation, and scale. |
| Map matching requires plausible transitions and sequence continuity, not only independent nearest points ([Newson & Krumm, 2009](https://doi.org/10.1145/1653771.1653818); [Bang et al., 2016](https://doi.org/10.3390/s16101768)). | Batched snapping is treated only as a cheap proxy. Guides are submitted to activity-specific Directions routing and whole-curve validation before they are labelled road-routed; a failed routing attempt remains an explicit manual-review fallback. |

These studies justify the architecture and metrics, but they do not prove that
a generated route is recognisable, safe, legal, or optimal in every city.
Thresholds remain engineering heuristics and should be calibrated with
labelled human-recognition tests. See the
[research notes](docs/gps-art-research.md) for the full evidence-to-algorithm
mapping and production funnel.

The built-in Leaflet editor exposes numbered draggable control points for every
candidate. After a correction, `/edit-route` routes the guide through the
activity-specific street graph again, recalculates quality and distance, and
returns a new GPX/TCX. If road routing is unavailable, the edited guide is
still exportable with a prominent manual-review warning.

Structured JSON logs are written to the console and, by default, to the
rotating `logs/gps-art-wizard.log`. Every HTTP request receives an
`X-Request-ID`, allowing UI reports, API failures, candidate measurements, and
provider errors to be correlated without logging API keys or the prompt text.
On Northflank, the production image writes only to the captured console stream.
The platform's native Loki log sink forwards that stream to Grafana Cloud,
where entries can be searched by request ID, event, severity, environment, or
release revision without placing Grafana credentials in the application.

Start with the [complete project guide](docs/README.md). Production operators
should also read the [deployment guide](docs/deployment.md). The dated
[2026-07-30 development and production lessons](docs/2026-07-30-lessons-learned.md)
record the first Northflank incidents, measured performance fix, Grafana
queries, and the operational troubleshooting checklist.

## Quick ideas

The web app keeps 12 simple, street-friendly starters beside the prompt and
places the full 32-idea catalog in a collapsible browser:

- **Simple shapes:** heart, star, circle, diamond, triangle, square, infinity,
  arrow, cross, lightning, wave, and moon
- **Nature:** flower, tree, mountain, and butterfly
- **Animals:** cat and dog
- **Symbols:** crown
- **Letters, numbers, and text:** A, C, L, M, N, S, U, V, Z, 2, 7, 42,
  and GPS

These presets favour continuous outlines, clear silhouettes, compact distances,
and cities whose curated route profiles are likely to offer a useful street
grid. They are starting points rather than guarantees: the result still depends
on the local street network, access rules, and route-provider coverage.

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,all]"
python -m uvicorn gps_art_wizzard.main:app --reload
```

The web client is then available after its Vite development server is started
from `frontend/`, or directly from FastAPI after `frontend/dist` has been built.

## Hosting

The recommended hobby deployment is the
[Northflank Developer Sandbox with Grafana Cloud Logs](docs/deployment.md#northflank-developer-sandbox).
A Northflank combined service builds the repository's multi-stage Dockerfile,
serves the SPA and API from one HTTPS `*.code.run` endpoint, and automatically
rebuilds the `master` branch after a push. The free Sandbox is always-on but
resource-limited and has no production SLA; the deployment guide records the
exact service, port, health-check, environment, and Loki-sink settings.

> Generated routes are planning candidates, not safety guarantees. Review every
> route against current access rules, crossings, closures, terrain, and local
> conditions before using it.

The historic “wizzard” spelling is retained in distribution, import, and
console-script identifiers for compatibility; public-facing copy uses the
conventional English spelling “wizard”.
