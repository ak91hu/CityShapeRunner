# GPS Art Wizard

Turn a run or ride into a recognisable drawing. Enter an idea such as “a heart
run in Budapest, about 8 km”, choose one of the 32 quick starts, or ask for a
city suggestion. The nine-agent pipeline interprets the request, creates and
places the outline, routes it over streets, measures shape likeness, tests
nearby alternatives, and retains every fully routed candidate. Quality gates
rank and warn rather than reject, so a user can compare, edit, and export a
weaker result with explicit review guidance.

Not sure what to draw? Ask the planner to suggest a suitable shape for a city:
“suggest a run in Debrecen, 10 km”. The planner uses available geographic
context to choose a template, placement, and orientation likely to fit the
street network.

## Quick-idea catalog

The centered generator shows 12 compact shapes first and keeps the full
32-idea catalog behind “Browse all” so the prompt remains the primary control.
Every preset uses a deterministic template or the built-in vector font:

| Group | Ideas |
|---|---|
| Simple shapes | Heart, star, circle, diamond, triangle, square, infinity, arrow, cross, lightning, wave, moon |
| Nature | Flower, tree, mountain, butterfly |
| Animals | Cat, dog |
| Symbols | Crown |
| Letters, numbers & text | A, C, L, M, N, S, U, V, Z, 2, 7, 42, GPS |

The selected city and distance in each preset are conservative starting points.
The catalog deliberately favours one-stroke or closed outlines; fragile
multi-part icons are omitted because routing the gaps can overwhelm their
silhouette. Multi-character text is reserved for a longer cycling preset.

The local Hungarian route catalogue includes Budapest, Debrecen, Szeged,
Miskolc, Pécs, Győr, Nyíregyháza, Kecskemét, Székesfehérvár, Szombathely,
Veszprém, Zalaegerszeg, Eger, Sopron, Tatabánya, Kaposvár, Szekszárd,
Békéscsaba, Cegléd, Siófok, and Keszthely. Each has an activity-specific,
city-tailored suggestion instead of a global circle/star fallback.

Inspired by [drawmyloop.com](https://drawmyloop.com/en), but with the painful
waypoint-by-waypoint plotting replaced by an autonomous agent pipeline.

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
| [Waschk and Krüger's automatic GPS-art planner](https://doi.org/10.1007/s41095-019-0146-z) shows that off-the-shelf routing can create large detours when drawing points lie off-grid, and proposes a graph cost that balances endpoint progress, path length, and distance from the intended segment. | Prefer a road-compatible placement before spending full route calls; then penalise detour stretch and deviation over the returned curve. | Hosted ORS does not expose the paper's custom edge cost. Preflight snapping plus post-route scoring is an approximation, not the same optimiser. |
| [Powałka's shape-guided route-finding thesis](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad) separates template placement from graph routing, generates and ranks alternatives, and demonstrates move/rotate/scale interaction with route feedback. | Search a broad transform space, preserve multiple candidates, and keep a human correction loop in the product. | Automatic search uses a bounded discrete sample—up to 180 transforms and seven full routes—rather than an exhaustive city graph search. |
| [Arkin et al.](https://doi.org/10.1109/34.75509) compare polygonal shapes through turning functions that can be normalised across translation, rotation, and scale. | Measure characteristic turns and their sequence in addition to shared-frame point similarity. | Turning similarity is one component; it cannot detect geographic displacement, unsafe roads, or an incorrect target distance by itself. |
| [Li and Fu](https://doi.org/10.3390/ijgi15030098) model road graphics with invariant turning angles and length ratios. Their experiments show that approximate line segments improve retrieval and that removing length-ratio constraints admits visibly deformed matches. | Preserve corners during guide-point reduction and score angular relations, extent, relative lengths, coverage, and collapse. | The app searches transformed templates and consumes ORS routes; it does not run the paper's road-network subgraph-retrieval algorithm. |
| [Nassir et al.](https://doi.org/10.3141/2430-18) treat overlap explicitly when constructing useful alternative-route choice sets. | Diversify the shortlist in transform space so scarce Directions calls cover distinct positions, orientations, and scales instead of near-duplicates. | Transform diversity is a proxy for route diversity; final candidates can still share streets where the network has few alternatives. |
| [Newson and Krumm](https://doi.org/10.1145/1653771.1653818) show that map matching must combine observation distance with plausible network transitions; pedestrian Fréchet work likewise emphasises ordered curve continuity ([Bang et al., 2016](https://doi.org/10.3390/s16101768)). | Treat nearest-edge snapping as non-authoritative and submit every edited guide to the activity profile before recomputing quality; only a successful Directions result is labelled road-routed. | ORS Directions establishes a connected routable result for its graph snapshot, but does not guarantee current legal access, surface quality, or personal safety. |

The resulting funnel is deliberately coarse-to-fine: up to 180 transforms are
reduced to curvature-preserving 18-point guides for one batched snap request;
a quality-and-diversity rule selects seven full Directions candidates; every
returned route is then evaluated using coverage, characteristic turns,
proportions, distance, closure, and road-routing evidence. Failed or weak
candidates remain visible with diagnostic warnings rather than being silently
discarded.

The literature supports these design choices, not the current numeric
thresholds. Those are explicit engineering heuristics and should be calibrated
against a labelled evaluation set in which independent reviewers identify the
intended figure and rate route usability. Full citations, the production
funnel, and the distinction between snapping and routing are documented in
[gps-art-research.md](gps-art-research.md).

| Agent | Responsibility |
|-------|----------------|
| **IntentAgent** | Parse the natural-language prompt into a structured intent (shape, city, sport, distance, text, suggest). Known template/text requests take a deterministic no-network fast path. |
| **PlanningAgent** | Resolve supported cities from the local route database, study curated geography, and commit street-grid rotation, safe offsets, and a distinct city/activity suggestion. |
| **ShapeAgent** | Turn the intent into a 2D polyline — 33 templates, a complete A–Z/0–9 vector font, short text outlines, or bounded LLM-drawn geometry. |
| **PlacementAgent** | Project the design at the target distance using sport- and shape-specific road-detour priors learned from measured ORS results. |
| **PreflightAgent** | Generate up to 180 city-wide translation/rotation/scale placements, batch-snap 18-point guides, retain every proxy result, and select seven high-quality but spatially/orientationally diverse alternatives for full routing. |
| **SnapAgent** | Route the drawing over the OpenRouteService street graph. Error-aware retries widen the radius only for missing-road errors and remove or simplify the exact unconnectable via-point for graph-connectivity errors. |
| **ValidationAgent** | Score shape fidelity, distance fit, and closure. Its below-threshold cap is monotonic, so recognisable geometry cannot tie a malformed distance-only match. |
| **RefinementAgent** | Consume the road-fit-ranked shortlist first, then bracket non-linear distance corrections and use local measured transforms only after the shortlist is exhausted. |
| **ExportAgent** | Serialise the selected candidate even below recommended targets. Unmatched or weak routes carry explicit review warnings instead of disappearing. |

The graph engine (`orchestrator.py`) wires these into a state machine with:
- a **planning step** (one strategy commit, read by shape + placement),
- a **coarse-to-fine placement search** (city-wide grid × six orientations ×
  three scales → one batched snap → diversity-aware seven-candidate full-route
  shortlist; all proxy and fully routed candidates remain available),
- a **refinement loop** (validate → take the next ranked placement or branch
  from the best → re-snap, up to eight iterations; candidate ranking balances
  the weakest export gate, repeated drafts are skipped, and regressions are
  discarded),
- a **provider fallback loop** (tries the configured provider order after an
  LLM error),
- a **shape fallback** (template → text → LLM-drawn, order set by the plan);
  if an unknown shape still cannot be drawn, the result is explicitly labelled
  as a fallback star and an error is recorded.

The result screen includes a candidate selector and a Leaflet route editor.
Numbered control points can be dragged and submitted to `POST /edit-route`;
the backend re-routes them with the selected activity profile, revalidates the
result, and returns a fresh GPX/TCX. Quality scores are recommendations, not
deletion rules.

HTTP middleware assigns or validates an `X-Request-ID` and emits structured
start/completion/failure events. Agent, ORS, validation, editing, and export
records inherit the same ID. JSON console logs and a rotating file log are
enabled by default; configure them with `LOG_LEVEL`, `LOG_FORMAT`, `LOG_FILE`,
`LOG_MAX_BYTES`, and `LOG_BACKUP_COUNT`. The production container leaves
`LOG_FILE` empty and emits host-independent JSON to stderr. Northflank captures
that stream and its native Loki log sink forwards it to Grafana Cloud without
exposing Grafana credentials to the application. Grafana Explore can filter
the JSON by request ID, event, severity, environment, or release revision. See
[deployment.md](deployment.md) for the exact service and log-sink setup.

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
editable/exportable as a guide, and carries an explicit manual-review warning.

## OpenCode Zen as the LLM

OpenCode Zen (`https://opencode.ai/zen/v1`) is the default provider — it is an
OpenAI-compatible gateway, so the existing OpenAI SDK is reused with a custom
`base_url`. Get a key at <https://opencode.ai/auth> (the same key you use in
opencode) and put it in `.env`:

```bash
OPENCODE_API_KEY=zen-...
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
LLM_MODEL=glm-5.2            # any /v1/chat/completions model: kimi-k2.6, deepseek-v4-flash, ...
LLM_PROVIDER=opencode
LLM_FALLBACK=opencode,anthropic,openai,ollama
```

Install the SDK: `pip install -e ".[opencode]"` (the `openai` package is shared
with the OpenAI provider).

## Web frontend

A Vite + React SPA lives in `frontend/`. It calls `/generate` and renders the
route on a Leaflet map, shows the validation score / refinement history, and
offers GPX/TCX downloads for eligible road-matched results.

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

Backend tests run offline when geocoding is disabled:

```bash
GEOCODE_OFFLINE=1 python -m pytest
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard
```

On PowerShell, set the variable with
`$env:GEOCODE_OFFLINE = "1"` before running pytest. Frontend build and browser
test commands are defined in `frontend/package.json`. The root CI workflow runs
the backend suite on Python 3.12 and 3.14, then builds the frontend and executes
its Playwright suite on Node.js 24.

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
[gps-art-research.md](gps-art-research.md), [deployment.md](deployment.md), and
the [2026-07-30 lessons learned](2026-07-30-lessons-learned.md) for the full
design, research basis, operating model, measured production incidents, and
troubleshooting checklist.
