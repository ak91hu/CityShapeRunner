# GPS Art Wizard

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

The built-in Leaflet editor exposes numbered draggable control points for every
candidate. After a correction, `/edit-route` routes the guide through the
activity-specific street graph again, recalculates quality and distance, and
returns a new GPX/TCX. If road routing is unavailable, the edited guide is
still exportable with a prominent manual-review warning.

Structured JSON logs are written to the console and, by default, to the
rotating `logs/gps-art-wizard.log`. Every HTTP request receives an
`X-Request-ID`, allowing UI reports, API failures, candidate measurements, and
provider errors to be correlated without logging API keys or the prompt text.

Start with the [complete project guide](docs/README.md). Production operators
should also read the [deployment guide](docs/deployment.md).

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

> Generated routes are planning candidates, not safety guarantees. Review every
> route against current access rules, crossings, closures, terrain, and local
> conditions before using it.

The historic “wizzard” spelling is retained in distribution, import, and
console-script identifiers for compatibility; public-facing copy uses the
conventional English spelling “wizard”.
