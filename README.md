# GPS Art Wizard

[![CI](https://github.com/ak91hu/CityShapeRunner/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ak91hu/CityShapeRunner/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-5FA04E?logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.140-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![Northflank ready](https://img.shields.io/badge/Northflank-ready-6C5CE7)](docs/deployment.md#northflank-developer-sandbox)
[![Grafana Cloud Logs](https://img.shields.io/badge/Grafana_Cloud-logs-F46800?logo=grafana&logoColor=white)](docs/deployment.md#persistent-and-searchable-grafana-cloud-logs)

Turn a run or ride into a drawing. Describe an idea—or choose from 158 catalog
options—and GPS Art Wizard tests the outline against real streets, compares
nearby placements and orientations, and shows how recognisable the resulting
route is. Only a route returned by the connected street router can reach the
download flow; a road-routed result that misses a quality target requires
explicit review.

The free-text planner sends the complete request directly to generation, where
the intent pipeline resolves the drawing, place, activity, and distance. In a
drawing request, `bug` always selects the insect template; a B route requires
an explicit `letter B` request. Optional controls can anchor the route at a
current location or address, set its first direction, avoid steps/ferries/fords, and prefer quieter
or greener walking streets. Result alternatives appear together as comparison
cards; route-readiness issues can be selected to zoom the map to their exact
preview segments.

The project combines 145 deterministic shape templates, a complete A–Z/0–9
vector font, local profiles for 50 major Hungarian cities, all 45 official Lake
Balaton shore municipalities, and 136 other European cities, optional LLM planning,
OpenRouteService street routing, quantitative shape validation, and guarded
GPX/TCX export. Every fully routed result is retained as a selectable candidate.
Quality thresholds rank and warn instead of deleting a fully routed result, so
lower-scoring street routes remain available for comparison, manual correction,
and reviewed export. A straight-line diagnostic is never exposed as a
selectable or downloadable GPS route.

The structured planner contains 230 unique destinations: Siófok belongs to both
the Hungarian top-50 and official Balaton coverage, but appears only once in the
picker. Every Balaton destination resolves locally and has its own placement
profile for shoreline, terrain, rail, road, and wetland constraints. See
[Lake Balaton coverage](docs/balaton-city-coverage.md) for the source, complete
list, and recommendation policy.

Sixteen additional one-stroke motifs—including paprika, puzzle cube, grey
cattle, water tower, thermal bath, and folk gate—are paired with practical
Hungarian-city starting points in the searchable catalog. Their research and
geometry audit are documented in
[Hungary-friendly GPS-art shapes](docs/hungarian-shape-catalog.md).

Free-form prompts are not limited to the picker. Common phrases such as
`draw a heart in Lyon, 8 km` can recover an unlisted settlement locally, then
Nominatim is restricted to inhabited-place results and its administrative bbox
is reduced to a bounded urban search area. Invalid coordinates fall back
explicitly instead of entering placement math.

Free-form drawings are not limited to the 158-option catalog either. A named
custom idea is preserved locally, converted into two structured vector
alternatives with an explicit recognition-feature brief, and checked for
degenerate proportions, transfer lines, duplicates, and self-intersections.
Compound requests reuse a related catalog contour as an anatomy/proportion
anchor without copying it unchanged. The preferred valid alternative wins;
both invalid alternatives trigger at most one bounded repair. Only successful
generated shapes enter the 128-entry cache. If no model is available, the
result uses an explicit full-word text fallback instead of reducing the request
to its initial or relabelling a
stock icon as the requested object. See the
[custom-shape research and decision record](docs/custom-shape-generation.md).

Route search is coarse-to-fine. Before spending Directions requests, one
batched road-snap preflight compares up to 180 city-wide
translation/rotation/scale placements. A quality-and-diversity selector sends
seven distinct alternatives to the full router, while every
preflight score remains in the diagnostics. Eighteen curvature-preserving
guide points per placement improve the proxy without adding Directions calls.
If Directions rejects the top-ranked placement, the orchestrator tries the
remaining road-fit shortlist before giving up. If none produces a connected
street polyline, `POST /generate` fails closed with HTTP 503 instead of placing
the original drawing over buildings, water, or other unroutable areas.

Recognition is evaluated from outline coverage, characteristic turns,
salient tips and notches, unintended U-turns, street-detour stretch, and
preserved proportions—not only average point distance. The map overlays the
intended dashed contour on the routed line. If
an explicitly requested drawing misses a recommended target, the planner
measures simpler city-aware templates and recommends the strongest result
without removing the original.

Generation remains a synchronous, quality-preserving search, so complex shapes
can take time. While it runs, the web app shows an elapsed timer, an animated
GPS-art route, rotating route-specific messages and facts, four illustrative
planning stages, and a cancel action. The stages communicate what normally
happens without claiming server-side percentage progress; reduced-motion
preferences disable the nonessential animation.

## GPS Art Intelligence

The result view now turns route generation into a repeatable local craft. Street
Canvas marks the strongest nearby placement areas from the preflight search;
Recognition Repair re-routes a drawing through its highest-information visual
anchors; and Time-aware Readiness combines daylight with an optional hourly
weather check. Groups can split one continuous route into balanced Community
GPS Mural sections with a GPX for each participant. Inkproof runs correlated
GPS-drift simulations before departure and highlights details likely to blur.
These analyses need no paid map call or account. The privacy model and endpoint
contracts are in
[GPS Art Intelligence](docs/gps-art-intelligence.md).

## Research basis

The pipeline is an engineering adaptation of published GPS-art, computational
geometry, route-choice, and map-matching research. It does not claim to
reproduce every paper's custom graph algorithm; instead, it maps the findings
to operations available through the hosted OpenRouteService API.

| Research finding | Consequence in GPS Art Wizard |
|---|---|
| Ordinary waypoint routers can turn off-network drawing points into large detours or visually destructive U-turns; GPS art benefits from a shape-aware graph cost ([Waschk & Krüger, 2019](https://doi.org/10.1007/s41095-019-0146-z)). | Placements are screened before Directions routing, curvature-bearing guide points are preserved, and a separate gate rejects doubled-back strokes absent from the drawing. |
| Template placement, graph search, candidate comparison, and interactive adjustment are complementary stages rather than one routing call ([Powałka, 2023](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad)). | A city-wide transform search produces several routed alternatives, while the browser editor lets the user correct control points and request a fresh route. |
| Turning functions compare polygonal shape in a way that can be normalised for translation, rotation, and scale ([Arkin et al., 1991](https://doi.org/10.1109/34.75509)). | Characteristic turns and their order contribute to recognition; mean point distance is never the sole likeness measure. |
| Turning angles, approximate road polylines, and internal length ratios help retrieve recognisable graphics and reject stretched lookalikes in road networks ([Li & Fu, 2026](https://doi.org/10.3390/ijgi15030098)). | Preflight and final validation score angular relations, extent, segment proportions, coverage, and collapse instead of accepting nearest-road distance alone. |
| European street networks vary substantially in orientation order, connectivity, segment length, and circuity ([Boeing, 2019](https://doi.org/10.1007/s41109-019-0189-1)). | Every catalogued city has a bounded local search area and obstacle-aware context; the transform search measures several positions and bearings rather than labelling an entire city “grid-like”. |
| Walkable and drivable networks can differ materially in circuity even within one city ([Boeing, 2017](https://arxiv.org/abs/1708.00836)). | Shape detail capacity is calculated separately for running and cycling and is combined with requested distance rather than treating activity as a display label. |
| Useful alternative sets must control overlap, or a top-*k* list can contain near-duplicates ([Nassir et al., 2014](https://doi.org/10.3141/2430-18)). | The seven expensive routing slots balance proxy quality with separation in position, rotation, and scale. |
| Map matching requires plausible transitions and sequence continuity, not only independent nearest points ([Newson & Krumm, 2009](https://doi.org/10.1145/1653771.1653818); [Bang et al., 2016](https://doi.org/10.3390/s16101768)). | Batched snapping is treated only as a cheap proxy. Guides are submitted to activity-specific Directions routing and whole-curve validation before they are labelled road-routed; failed placements trigger the remaining shortlist, and an exhausted search returns no GPS export. |

These studies justify the architecture and metrics, but they do not prove that
a generated route is recognisable, safe, legal, or optimal in every city.
Thresholds remain engineering heuristics and should be calibrated with
labelled human-recognition tests. See the
[research notes](docs/gps-art-research.md) for the full evidence-to-algorithm
mapping and production funnel. The latest method-by-method review and the
implemented geometry changes are recorded in the
[August 2026 algorithm audit](docs/gps-art-algorithm-audit-2026-08.md).

## Understanding and editing results

The candidate comparison cards keep every fully routed result for the final
chosen shape visible together. Routes that pass every automatic check appear first; a larger average
score cannot outrank a route that passes all of the independent recognition,
road, distance, and closure checks. Attempts for a different suggested shape
remain in the audit summary instead of being mixed into that selector.

“Automatic checks passed” means only that the route met the application's
documented engineering thresholds. It is not scientific proof of
recognisability, legality, accessibility, or safety. A route that misses a
target remains selectable and exportable after the user reviews and explicitly
accepts that exact geometry, but only when Directions returned a connected
street route. A straight-line diagnostic returned internally without road
routing never enters the API candidate selector, and the public response never
contains downloadable GPX/TCX data for it.

The built-in Leaflet editor exposes numbered draggable control points for every
candidate. After a correction, `/edit-route` routes the guide through the
activity-specific street graph again, recalculates quality and distance, and
returns a new GPX/TCX only after successful street routing. If routing is
unavailable or the edited points cannot be connected, `/edit-route` returns
HTTP 503 and creates no GPS file. Moving a point marks the editor as having
pending changes and disables downloads until the user updates the street route
or discards those changes; closing an unchanged editor does not imply that
anything was discarded.

The complete map can also be rotated manually from −180° to 180°, in 1° slider
steps or 15° buttons, with a one-click north-up reset. Tiles, intended outline,
street route, and markers share the same bearing. Gallery capture uses the same
geographic tile transform, so a published image keeps the orientation chosen
in the result viewer.

Structured JSON logs are written to the console and, by default, to the
rotating `logs/gps-art-wizard.log`. Every HTTP request receives an
`X-Request-ID`, allowing UI reports, API failures, candidate measurements, and
provider errors to be correlated without logging API keys or the prompt text.

An optional anonymous gallery captures the already-rendered Leaflet map as a
PNG, retaining street names, the route overlay, and visible OpenStreetMap
attribution. Signed server-side Cloudinary uploads and Cloudinary asset search
provide storage and listing without a gallery database. Publishing is opt-in
because the exact mapped location becomes public; gallery uploads never include
the prompt, request ID, GPX/TCX document, or user profile. Configure the
server-only `CLOUDINARY_URL` to enable it. The browser stores only the matching
removal capability for images published from that browser; failure to retain
that local token does not turn a successful upload into a failed publication.
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

The web app keeps six common starters beside the prompt and places a searchable
158-option catalog behind “More shapes, letters, and numbers”. It contains 145
deterministic route templates plus 13 letter, number, and short-text presets:

- **Hungarian ideas (16):** paprika, puzzle cube, moustache, grape cluster,
  wine glass, cauldron, horseshoe, wheat, suspension bridge, water tower,
  grey cattle, stag, pomegranate, chimney cake, thermal bath, and folk gate
- **Simple shapes (19):** heart, star, circle, diamond, triangle, square,
  infinity, arrow, cross, lightning, wave, moon, hexagon, octagon, teardrop,
  shield, clover, spiral, and hourglass
- **Nature (23):** the original 16 plus acorn, banana, broccoli, feather,
  ice cream, volcano, and watermelon slice
- **Animals (33):** the original 20 (including the insect-aware bug template)
  plus ant, crab, dinosaur, frog, hedgehog,
  koala, octopus, paw print, seahorse, snake, spider, squid, and swan
- **Objects (44):** the original 14 plus 30 route-authored everyday objects,
  including robot, lighthouse, camera, paper plane, train, and windmill
- **Symbols (10):** crown, skull, DNA helix, speech bubble, location pin,
  chess pawn, compass, ghost, lock, and medal
- **Letters, numbers, and text:** A, C, L, M, N, S, U, V, Z, 2, 7, 42,
  and GPS

The complex templates are single continuous silhouettes wherever possible,
preserve recognisable high-curvature landmarks, and use longer cycling starts
when their detail needs more road-network resolution. They are starting points,
not guarantees: the result still depends on local connectivity, access rules,
and route-provider coverage. Cat, dog, bird, and bat now have separate
route-readable outlines and distinct catalog markers. A rotation-, scale-,
start-, and direction-independent audit checks every pair in the 145-template
registry; see the [shape-template research and uniqueness guard](docs/shape-template-uniqueness.md).

The structured city picker follows the [KSH 2025 list of Hungary's 50 largest
settlements](https://www.ksh.hu/stadat_files/fol/en/fol0014.html). Each resolves locally without a public-geocoder call and has a
bounded urban search area; obstacle descriptions guide the first placement,
while measured preflight and Directions routing remain authoritative.

The Europe group now contains 136 regionally balanced cities guided by the
[Eurostat city-statistics framework](https://ec.europa.eu/eurostat/web/cities/methodology).
The original 30 are joined by 106 cities across western, northern, central,
eastern, and south-eastern Europe. Every entry resolves offline to a compact
urban search box and one of the documented grid, radial, river, coast, lake,
hill, or mountain recommendation profiles. These are planning priors, not a
claim that every neighbourhood is suitable for every drawing.

Smart suggestions no longer use a fixed city mascot. The planner measures all
145 route templates, combines their continuity, turning complexity, directional
order, aspect ratio, and routeability with the selected city's street context,
activity, and distance, then sends three diverse continuous shapes through the
real placement and routing checks. The result explains why the winning shape
was shortlisted. See the [city–shape recommendation audit](docs/city-shape-recommendations.md).

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,all]"
python -m uvicorn gps_art_wizzard.main:app --reload
```

The web client is then available after its Vite development server is started
from `frontend/`, or directly from FastAPI after `frontend/dist` has been built.

## Testing

The backend suite is deterministic and runs without paid providers. The UI
suite uses Playwright with mocked API, map-tile, and gallery responses, and runs
every functional scenario in desktop and mobile Chromium.

```bash
GEOCODE_OFFLINE=1 python -m pytest -q
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard

cd frontend
npm ci
npm run build
npm run test:e2e
```

On Windows PowerShell, use `$env:GEOCODE_OFFLINE = "1"` before pytest. Install
the browser once with `cd frontend && npx playwright install chromium`. See the
[testing guide](docs/testing.md) for targeted commands, suite ownership,
Playwright debugging, and the Windows temporary-directory workaround.

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
