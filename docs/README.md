# GPS Art Wizard

Enter an idea such as “heart, Budapest, running, 8 km”, choose one of 157 catalog
options, or enter a city, activity, and distance. The planner creates and places
the outline, routes it over streets, measures the match, and retains every fully
routed candidate. Candidates that pass all independent shape, street, distance,
and closure checks rank first and download immediately. Other candidates require
explicit review and acceptance. Attempts for a different suggested shape remain
available in the audit summary.

The free-text field is not limited to the catalog. Named custom drawings keep
their full description, use two bounded model-generated vector alternatives
plus explicit recognition features when a provider is available, and pass
executable topology checks before routing. Compound descriptions receive a
related catalog contour as a structure anchor. A
failed or unavailable generator produces an explicitly labelled, idea-linked
fallback instead of pretending that a stock icon is the requested object. See
[Custom free-text shape generation](custom-shape-generation.md) for the research,
decision pipeline, security boundaries, and remaining limitations.

A public image link can also be used as the drawing source. SVG and every
raster format supported by the installed Pillow build are normalised into a
small AI-ready reference; one multimodal OpenCode call then analyses the whole
visible subject and creates two route-native GPS-art alternatives. SVG sampling
remains available only as a deterministic fallback when AI is unavailable.

For a city-based suggestion, enter:
“suggest a run in Debrecen, 10 km”. The planner uses available geographic
context to choose a template, placement, and orientation likely to fit the
street network.

The choice is computed from the full 144-template registry rather than a fixed
city-to-symbol table. Shape continuity, turns, directional order, proportions,
and detail are scored against city grid/connectivity, barriers, terrain,
activity, and requested distance. Up to three diverse continuous templates are
then measured on the actual route graph. The result includes a concise reason;
the full method and coverage groups are in
[City-aware shape recommendations](city-shape-recommendations.md).
The research and route-design rationale for the 16 locally themed additions is
in [Hungary-friendly GPS-art shapes](hungarian-shape-catalog.md).

The city picker exposes 230 unique destinations. This includes every one of the
45 shore municipalities in the current Lake Balaton statutory list; Siófok is
shown only in the Hungary group to avoid a duplicate option. The legal scope,
complete list, local geocoding approach, and shore-specific planning constraints
are documented in [Lake Balaton city coverage](balaton-city-coverage.md).

## Quick-idea catalog

The planner shows six common shapes first and keeps the full searchable
157-option catalog behind “More shapes, letters, and numbers” so the prompt
remains the primary control. The catalog combines 144 deterministic route
templates with 13 built-in vector-font presets:

| Group | Ideas |
|---|---|
| Hungarian ideas | Paprika, puzzle cube, moustache, grape cluster, wine glass, cauldron, horseshoe, wheat, suspension bridge, water tower, grey cattle, stag, pomegranate, chimney cake, thermal bath, folk gate |
| Simple shapes | Heart, star, circle, diamond, triangle, square, infinity, arrow, cross, lightning, wave, moon, hexagon, octagon, teardrop, shield, clover, spiral, hourglass |
| Nature | Original nature set plus acorn, banana, broccoli, feather, ice cream, volcano, and watermelon slice |
| Animals | Original animal set plus ant, crab, dinosaur, frog, hedgehog, koala, octopus, paw print, seahorse, snake, spider, squid, and swan |
| Objects | Original object set plus 30 single-outline subjects, including robot, lighthouse, camera, paper plane, train, and windmill |
| Symbols | Crown, skull, DNA helix, speech bubble, location pin, chess pawn, compass, ghost, lock, medal |
| Letters, numbers & text | A, C, L, M, N, S, U, V, Z, 2, 7, 42, GPS |

The selected city and distance in each preset are conservative starting points.
Complex templates use one continuous silhouette wherever possible, retain
their most informative corners and notches, and start at longer distances when
their detail needs more streets. Multi-character text uses a longer cycling
preset. The cat, dog, bird, and bat have separate route-readable silhouettes;
an invariant full-catalog audit prevents two canonical names from encoding the
same route target. See [Recognisable and unique GPS-art templates](shape-template-uniqueness.md).

The structured city picker covers the 50 largest Hungarian settlements in the
[KSH 2025 population table](https://www.ksh.hu/stadat_files/fol/en/fol0014.html).
All 50 resolve from the local route catalogue without a public Nominatim call.
The 12 newly completed profiles are Érd, Szolnok, Szigetszentmiklós, Ózd,
Hajdúböszörmény, Budaörs, Kiskunfélegyháza, Ajka, Szentes, Gyál, Dunaharaszti,
and Tata. Each profile constrains the city-wide search and describes major
water, terrain, or infrastructure barriers; measured road-network checks still
decide which placement is usable.

The separate Europe group contains 136 regionally balanced cities guided by
the [Eurostat city-statistics coverage](https://ec.europa.eu/eurostat/web/cities/methodology).
The 106 new entries span western, northern, central, eastern, and south-eastern
Europe. Every city resolves locally to a bounded urban search box and a
deterministic street-network profile. The list is a reproducible product-
coverage sample, not a population ranking or a guarantee of route suitability.

The interaction model was informed by [drawmyloop.com](https://drawmyloop.com/en).
GPS Art Wizard automates initial placement and keeps manual route-point editing
available for corrections.

## How it works

```
prompt ─▶ IntentAgent ─▶ PlanningAgent ─▶ ShapeAgent ─▶ PlacementAgent ─▶ PreflightAgent ─▶ SnapAgent ─▶ ValidationAgent ─▶ ExportAgent
                                  ▲                              │ shortlist                    │
                                  │                              └──────── RefinementAgent ◀────┘  (bounded measured loop)
                                  │   skills loaded into every LLM agent's prompt from docs/
```

## Research-derived design decisions

GPS-art generation is a constrained shape-matching problem on a legal,
activity-specific road graph—not ordinary waypoint routing. The implementation
uses the following evidence-to-design mapping:

| Evidence | Result used by the application | Implementation boundary |
|---|---|---|
| [Waschk and Krüger's automatic GPS-art planner](https://doi.org/10.1007/s41095-019-0146-z) shows that off-the-shelf routing can create large detours and repeated U-turns when drawing points lie off-grid, and proposes a graph cost that balances endpoint progress, path length, and distance from the intended segment. | Prefer a road-compatible placement before spending full route calls; then independently reject unintended doubled-back strokes as well as detour stretch and deviation. | Hosted ORS does not expose the paper's custom edge cost. Preflight snapping plus post-route scoring is an approximation, not the same optimiser. |
| [Powałka's shape-guided route-finding thesis](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad) separates template placement from graph routing, generates and ranks alternatives, and demonstrates move/rotate/scale interaction with route feedback. | Search a broad transform space, preserve multiple candidates, and keep a human correction loop in the product. | Automatic search uses a bounded discrete sample—up to 180 transforms and seven full routes—rather than an exhaustive city graph search. |
| [Arkin et al.](https://doi.org/10.1109/34.75509) compare polygonal shapes through turning functions that can be normalised across translation, rotation, and scale; [Feldman and Singh](https://doi.org/10.1037/0033-295X.112.1.243) show why high-curvature and concave contour regions carry disproportionate information. | Measure characteristic turns and multiscale salient corners/notches/tips in addition to shared-frame point similarity. | These are components, not substitutes for geographic displacement, access, distance, or safety checks. |
| [Li and Fu](https://doi.org/10.3390/ijgi15030098) model road graphics with invariant turning angles and length ratios. Their experiments show that approximate line segments improve retrieval and that removing length-ratio constraints admits visibly deformed matches. | Preserve corners during guide-point reduction and score angular relations, extent, relative lengths, coverage, and collapse. | The app searches transformed templates and consumes ORS routes; it does not run the paper's road-network subgraph-retrieval algorithm. |
| [Boeing](https://doi.org/10.1007/s41109-019-0189-1) measures substantial differences in street orientation, connectivity, circuity, and segment structure across cities. | Give every supported European city its own search bounds and barrier context, then test multiple rotations and placements. | City-level morphology does not prove neighbourhood- or activity-specific routability; preflight and Directions remain authoritative. |
| [Nassir et al.](https://doi.org/10.3141/2430-18) treat overlap explicitly when constructing useful alternative-route choice sets. | Diversify the shortlist in transform space so scarce Directions calls cover distinct positions, orientations, and scales instead of near-duplicates. | Transform diversity is a proxy for route diversity; final candidates can still share streets where the network has few alternatives. |
| [Newson and Krumm](https://doi.org/10.1145/1653771.1653818) show that map matching must combine observation distance with plausible network transitions; pedestrian Fréchet work likewise emphasises ordered curve continuity ([Bang et al., 2016](https://doi.org/10.3390/s16101768)). | Treat nearest-edge snapping as non-authoritative and submit every edited guide to the activity profile before recomputing quality; only a successful Directions result is labelled road-routed. | ORS Directions establishes a connected routable result for its graph snapshot, but does not guarantee current legal access, surface quality, or personal safety. |

The resulting funnel is deliberately coarse-to-fine: up to 180 transforms are
reduced to curvature-preserving 18-point guides for one batched snap request;
a quality-and-diversity rule selects seven full Directions candidates; every
returned route is then evaluated using coverage, characteristic turns,
salient curvature landmarks, extra reversal events, proportions, distance, closure, and road-routing
evidence. A failed component cannot be hidden by the aggregate score. Weak
final-shape attempts remain selectable for comparison and correction;
different-shape attempts remain counted—with their failed gates—in the
candidate audit instead of being mixed into the selector.

The literature supports these design choices, not the current numeric
thresholds. Those are explicit engineering heuristics and should be calibrated
against a labelled evaluation set in which independent reviewers identify the
intended figure and rate route usability. Full citations, the production
funnel, and the distinction between snapping and routing are documented in
[gps-art-research.md](gps-art-research.md).
The concrete method-by-method review and current geometry improvements are in
the [August 2026 algorithm audit](gps-art-algorithm-audit-2026-08.md).

| Agent | Responsibility |
|-------|----------------|
| **IntentAgent** | Parse the natural-language prompt into a structured intent (shape, city, sport, distance, text, suggest). Known template/text requests take a deterministic no-network fast path. |
| **PlanningAgent** | Resolve supported cities from the local route database, study curated geography, and commit street-grid rotation, safe offsets, and a distinct city/activity suggestion. |
| **ShapeAgent** | Turn the intent into a 2D polyline — 144 templates, a complete A–Z/0–9 vector font, short text outlines, or two schema-bounded LLM alternatives with catalog-guided structure and executable validation. |
| **PlacementAgent** | Project the design at the target distance using sport- and shape-specific road-detour priors learned from measured ORS results. |
| **PreflightAgent** | Generate up to 180 city-wide translation/rotation/scale placements, batch-snap 18-point guides, retain every proxy result, and select seven high-quality but spatially/orientationally diverse alternatives for full routing. |
| **SnapAgent** | Route the drawing over the OpenRouteService street graph. Error-aware retries widen the radius only for missing-road errors and remove or simplify the exact unconnectable via-point for graph-connectivity errors. |
| **ValidationAgent** | Score shared-frame shape fidelity—including multiscale salient landmarks and unintended reversal events—plus distance fit and closure. Its below-threshold cap is monotonic, so recognisable geometry cannot tie a malformed distance-only match. |
| **RefinementAgent** | Consume the road-fit-ranked shortlist first, then bracket non-linear distance corrections and use local measured transforms only after the shortlist is exhausted. |
| **ExportAgent** | Serialise the full selected-shape geometry. Routes that pass every automatic check download immediately; below-target routes require explicit user acceptance after reviewing the measurements. |

The graph engine (`orchestrator.py`) wires these into a state machine with:
- a **planning step** (one strategy commit, read by shape + placement),
- a **coarse-to-fine placement search** (city-wide grid × six orientations ×
  three scales → one batched snap → diversity-aware seven-candidate full-route
  shortlist; all proxy and fully routed attempts remain auditable, while every
  final selected-shape route remains selectable and clearly labelled),
- a **refinement loop** (validate → take the next ranked placement or branch
  from the best → re-snap, up to eight iterations; candidate ranking balances
  the weakest export gate, repeated drafts are skipped, and regressions are
  discarded),
- a **provider fallback loop** (tries the configured provider order after an
  LLM error),
- a **shape fallback** (template → text → validated model-drawn geometry, order
  set by the plan); invalid generated geometry gets one bounded repair attempt,
  then the complete requested phrase is rendered as an explicitly labelled
  fallback rather than being reduced to its initial.

The result screen includes a candidate selector and a Leaflet route editor.
The selector ranks routes that pass every automatic check ahead of review
routes, even when a failed route has a higher aggregate score. “Checks passed”
is an engineering result, not a scientific, legal, accessibility, or safety
guarantee. The compact screen explains the 0–100 indices and shows every gate,
measured value, threshold, route/guide point count, distance error, detour ratio,
closure gap, mean outline deviation, and placement transform. Below-target and
non-road-routed guides remain exportable only after explicit acceptance.

The map has an accessible −180°…180° rotation slider, 15° step controls, and a
north-up reset. The entire geographic view rotates together, and gallery PNG
capture preserves the chosen bearing.

Numbered control points can be dragged and submitted to `POST /edit-route`;
the backend re-routes them with the selected activity profile, revalidates the
result, and returns full GPX/TCX geometry with an automatic-check report. A
point move creates pending editor state, so downloads are disabled until the
user updates the street route or discards the move. The editor button says
“Close editor” when nothing changed and “Discard point changes” only when a
move would actually be lost. Each rebuilt route receives a stable ID so its
acceptance state applies only to that exact geometry.

When Cloudinary is configured, a road-routed candidate that has passed the
checks or been accepted can be published to the anonymous image gallery after
separate location-disclosure consent. The upload contains the visible map,
street labels, route, markers, and OpenStreetMap attribution—not the prompt,
request ID, GPX/TCX, or user identity. Removal tokens are stored only in the
publishing browser; local-storage failure does not misreport a completed
server-side upload or deletion as failed.

HTTP middleware assigns or validates an `X-Request-ID` and emits structured
start/completion/failure events. Agent, ORS, validation, editing, and export
records inherit the same ID. JSON console logs and a rotating file log are
enabled by default. Validation, candidate, edit, final-decision, and export
events include readable summaries plus searchable component scores, failed
gates, transforms, point counts, and export mode. Configure them with
`LOG_LEVEL`, `LOG_FORMAT`, `LOG_FILE`,
`LOG_MAX_BYTES`, and `LOG_BACKUP_COUNT`. The production container leaves
`LOG_FILE` empty and emits host-independent JSON to stderr. Northflank captures
that stream and its native Loki log sink forwards it to Grafana Cloud without
exposing Grafana credentials to the application. Grafana Explore can filter
the JSON by request ID, event, severity, environment, or release revision. See
[deployment.md](deployment.md) for the exact service and log-sink setup.
The UI also records `route.user.accepted` through `POST /route-acceptance`
when a user explicitly chooses a below-target route; this event contains the
decision metrics and IDs but never uploads the route geometry.

**Skills**: every agent's system prompt is augmented at runtime with the
relevant markdown from `docs/skill-*.md` (shape design, placement, snap, metrics,
refinement, planning, prompt discipline). These skill files are the runtime
source of truth and are loaded during prompt construction — see
`skills/loader.py`.

## Requirements and quick start

- Python 3.12 or newer
- Node.js 24 for frontend development and production builds
- An OpenRouteService key for road-following routes
- Optionally, a supported LLM provider key for AI planning

```bash
python -m venv .venv
. .venv/bin/activate                           # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,all]"

cp .env.example .env                           # Windows: Copy-Item .env.example .env
python scripts/run_demo.py
python -m uvicorn gps_art_wizzard.main:app --reload
```

The pipeline runs **even without any API key**: LLM calls fall back to
deterministic rules, and the snap step uses a straight-line fallback when no
ORS key is set. A straight-line fallback is marked `snapped=false`, remains
editable as a diagnostic guide, carries an explicit warning, and can be
downloaded only after the user explicitly accepts the shown geometry. It is
not represented as a road-following route.

## OpenCode Zen as the LLM

OpenCode Zen (`https://opencode.ai/zen/v1`) is the default provider — it is an
OpenAI-compatible gateway, so the existing OpenAI SDK is reused with a custom
`base_url`. Get a key at <https://opencode.ai/auth> (the same key you use in
opencode) and put it in `.env`:

```bash
OPENCODE_API_KEY=zen-...
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_STRUCTURED_MODEL=gpt-5.4-mini # /v1/responses, fast multimodal strict-schema tasks
LLM_MODEL=glm-5.2            # any /v1/chat/completions model: kimi-k2.6, deepseek-v4-flash, ...
LLM_PROVIDER=opencode
LLM_FALLBACK=opencode,anthropic,openai,ollama
```

`LLM_MODEL` remains the general chat model. Strictly structured jobs such as
unknown-shape contour generation use `OPENCODE_STRUCTURED_MODEL` through Zen's
Responses endpoint. This prevents a reasoning-heavy chat model from consuming
the output limit before it emits the required coordinate JSON.

Install the SDK: `pip install -e ".[opencode]"` (the `openai` package is shared
with the OpenAI provider).

## Web frontend

A Vite + React SPA lives in `frontend/`. It calls `/generate` and renders the
route on a rotatable Leaflet map, shows the validation score / refinement history, and
offers immediate GPX/TCX downloads for routes that pass every automatic check.
Review routes and non-road-routed guides use the explicit acceptance flow.

Dev (hot-reload frontend on :5173, API on :8000):

```bash
python -m uvicorn gps_art_wizzard.main:app --reload # backend
cd frontend && npm install && npm run dev          # frontend
```

Production (single process — FastAPI serves the built SPA at `/`):

```bash
cd frontend && npm run build                       # outputs frontend/dist
cd .. && python -m uvicorn gps_art_wizzard.main:app # http://127.0.0.1:8000
```

The SPA mount is a catch-all registered after `/health`, `/generate`, and
`/docs`, so those keep working. CORS for the Vite dev server is configured via
`WEB_CORS_ORIGINS` (defaults to `http://localhost:5173,http://127.0.0.1:5173`).
For a non-root, multi-stage production image and operational settings, see
[deployment.md](deployment.md).

## Tests and quality checks

Backend tests run offline when geocoding is disabled. Playwright starts its own
Vite server and replaces backend, map-tile, and gallery traffic with
deterministic fixtures:

```bash
GEOCODE_OFFLINE=1 python -m pytest
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard

cd frontend
npm ci
npm run build
npm run test:e2e
```

On PowerShell, set the variable with
`$env:GEOCODE_OFFLINE = "1"` before running pytest. Install the Playwright
browser once with `npx playwright install chromium` if it is not already
present. The root CI workflow runs the backend suite on Python 3.12 and 3.14,
then builds the frontend and executes its Playwright suite on Node.js 24.
The [testing guide](testing.md) describes the test layers, targeted commands,
current API-contract and browser-workflow coverage, failure artifacts, and the
workspace-local pytest temporary-directory workaround for restricted Windows
profiles.

## Safety and limitations

GPS-art generation balances several competing constraints. A high visual score
does not establish legal access, personal safety, suitable surface, acceptable
traffic, current opening hours, or the absence of temporary closures. Inspect
every result on a current map and adapt it to local conditions before exporting
it to a navigation or activity service.

The historic “wizzard” spelling is retained in distribution, import, and
console-script identifiers for compatibility; public-facing copy uses the
conventional English spelling “wizard”.

## Layout

```
gps_art_wizzard/
  llm/         provider-agnostic LLM interface (opencode/zen, openai, anthropic, ollama, factory w/ fallback)
  agents/      one module per agent + BaseAgent (intent, planning, shape, placement, preflight, snap, validation, refinement, export)
  skills/      loads docs/skill-*.md into agent prompts (loader)
  prompts/     prompt templates + registry (system, intent, plan, shape, refinement)
  tools/       geo math, shape library, text shapes, ORS client, geocoder, GPX writer, similarity
  api/         FastAPI routes
  state.py     the workflow state object passed between agents
  orchestrator.py   the graph/loop engine
  main.py      FastAPI entrypoint (CORS + SPA serving)
frontend/      Vite + React SPA (Leaflet map, prompt form, GPX/TCX download)
docs/          project, architecture, deployment, and agent-skill documentation
```

See [AGENTS.md](AGENTS.md), [architecture.md](architecture.md),
[gps-art-research.md](gps-art-research.md),
[gps-art-algorithm-audit-2026-08.md](gps-art-algorithm-audit-2026-08.md),
[production-gallery-testing.md](production-gallery-testing.md),
[city-shape-recommendations.md](city-shape-recommendations.md),
[ui-ux-rationale.md](ui-ux-rationale.md),
[deployment.md](deployment.md), and
the [2026-07-30 lessons learned](2026-07-30-lessons-learned.md) for the full
design, research basis, operating model, measured production incidents, and
troubleshooting checklist.
