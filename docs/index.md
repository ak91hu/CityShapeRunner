# Paceasso engineering guide

**GPS Art Wizzard** is the product subtitle.

<div class="hero" markdown>

# Draw with streets, not across them

Paceasso turns a natural-language drawing idea into a route that follows a connected, routable street network. This site is the maintained engineering reference for the Python API, React client, route-generation pipeline, quality gates, deployment, and operations.

[Start developing](guides/getting-started.md){ .md-button .md-button--primary }
[Explore the architecture](architecture/overview.md){ .md-button }

</div>

## System contract

The product deliberately separates an **ideal drawing** from a **usable route**. The ideal geometry is a guide for placement and similarity scoring; only geometry returned by the routing provider may become an exportable activity route.

!!! danger "Fail-closed street-routing invariant"

    `/generate` and `/edit-route` must not return a GPX/TCX track when the route cannot be matched to connected streets. Routing failures produce HTTP `503`, rather than falling back to straight segments that can cross buildings, water, or inaccessible land.

The API still returns quality and readiness information for a routed result. Automatic checks help compare candidates, but do not replace checking live closures, access rules, traffic, weather, or personal ability.

## Documentation map

Documentation has one maintained home, organized by purpose:

| Folder | Contents |
|---|---|
| `guides/` | Getting started, product capabilities and city coverage |
| `architecture/` | Pipeline contracts, algorithms and implementation diagrams |
| `reference/` | API, configuration, integrations and catalogs |
| `development/` | Development workflow, review method and testing |
| `operations/` | Deployment, CI/CD and production checks |
| `design/` | UI design decisions and product plans |
| `research/` | Research sources, positioning and asset provenance |
| `reports/` | Dated audits, historical measurements and lessons |
| `skills/` | Runtime agent prompts, loaded by the application |

The root `README.md` introduces the repository, and root `AGENTS.md` is its
development-agent entry point. Tool-discovered `.agents/skills/*/SKILL.md` and
`.github/pull_request_template.md` retain their required locations. All other
maintained Markdown belongs in the folders above; generated reports belong in
the ignored `test-results/` folder.

[Development and Ponytail workflow](development/workflow.md) ·
[UI design](design/ui-design.md) ·
[Webapp and documentation review](reports/2026-10-26-webapp-review.md) ·
[Usability audit](reports/2026-10-19-usability.md) ·
[GPS-art generation review](research/2026-10-19-generation-review.md)

<div class="doc-grid" markdown>

<div class="doc-card" markdown>

### Build and run

Install the two runtimes, configure providers, start the API and SPA, and send a first request.

[Developer quick start](guides/getting-started.md)

</div>

<div class="doc-card" markdown>

### Understand the pipeline

Follow intent parsing, shape design, placement search, street routing, validation, refinement, and export.

[Implementation guide](architecture/implementation/index.md) · [System architecture](architecture/overview.md)

[Algorithmic background](architecture/algorithmic-background.md) explains the search budgets,
geometry comparison, scoring formulas, and export gates behind the pipeline.

</div>

</div>

## Implementation at a glance

```mermaid
flowchart LR
    UI[React planner] -->|POST /generate| API[FastAPI boundary]
    API --> INTENT[Intent + planning]
    INTENT --> SHAPE[Route-native shape]
    SHAPE --> SEARCH[Placement preflight]
    SEARCH --> ORS[Street routing]
    ORS --> QUALITY[Independent quality gates]
    QUALITY -->|pass or street-routed review| RESULT[Map + GPX/TCX]
    QUALITY -->|no connected streets| BLOCK[HTTP 503 · no export]

    classDef primary fill:#e7f2ed,stroke:#08705d,color:#153d35,stroke-width:2px;
    classDef accent fill:#fff0eb,stroke:#d95d39,color:#5c2a1c,stroke-width:2px;
    class UI,API,INTENT,SHAPE,SEARCH,ORS,QUALITY,RESULT primary;
    class BLOCK accent;
```

The [engineering overview](architecture/implementation/index.md) links every box to its owning module and expands the system into backend sequence, state/class, frontend state-machine, and runtime topology diagrams.

## Connected services at a glance

<div class="integration-ribbon" aria-label="External services used by Paceasso">
  <span><strong>ORS</strong> street routing</span>
  <span><strong>OSM</strong> places and tiles</span>
  <span><strong>AI</strong> four model adapters</span>
  <span><strong>WX</strong> hourly readiness</span>
  <span><strong>CLD</strong> optional gallery</span>
</div>

<figure class="api-ecosystem-figure api-ecosystem-compact">
  <img src="assets/api-ecosystem.svg" alt="Visual overview of the external API ecosystem around the FastAPI service.">
</figure>

The [external API integration guide](reference/external-apis.md) explains every provider endpoint, payload, credential boundary, timeout, retry strategy, usage policy, and degradation path.

<div class="doc-grid" markdown>

<div class="doc-card" markdown>

### Integrate with the API

Use the request models, response fields, error semantics, request correlation, and interactive OpenAPI UI.

[HTTP API reference](reference/api-reference.md) · [External integrations](reference/external-apis.md)

</div>

<div class="doc-card" markdown>

### Configure safely

Review every provider, routing, workflow, server, gallery, export, and logging setting with its default and scope.

[Configuration reference](reference/configuration-reference.md)

</div>

<div class="doc-card" markdown>

### Protect behavior

Run backend unit/integration tests, browser-level functional tests, static analysis, and strict documentation builds.

[Testing guide](development/testing.md)

</div>

<div class="doc-card" markdown>

### Release and operate

Understand the Northflank application release and the gated GitHub Pages documentation release.

[CI/CD](operations/ci-cd.md) · [Production deployment](operations/deployment.md)

</div>

</div>

## Repository at a glance

| Area | Path | Responsibility |
| --- | --- | --- |
| API and runtime | `gps_art_wizzard/main.py`, `gps_art_wizzard/api/` | FastAPI app, request correlation, validation, public HTTP contracts |
| Orchestration | `gps_art_wizzard/orchestrator.py`, `gps_art_wizzard/graph.py` | Candidate generation, agent ordering, refinement loop |
| Domain agents | `gps_art_wizzard/agents/` | Intent, planning, shape, placement, snapping, validation, export |
| Geospatial tools | `gps_art_wizzard/tools/` | Geocoding, ORS integration, geometry, catalog, GPX/TCX, gallery |
| Web client | `frontend/src/` | React workflow, route map, result comparison and editing |
| Automated checks | `tests/`, `frontend/tests/` | Python and Playwright regression suites |
| Documentation | `docs/`, `mkdocs.yml` | MkDocs source, navigation, design, technical reference |
| Delivery | `.github/workflows/ci.yml`, `Dockerfile` | CI gates, Pages publication, production image |

## Fast verification

```powershell
# Backend quality gates
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard
$env:GEOCODE_OFFLINE = "1"
python -m pytest -q

# Frontend build and functional tests
Set-Location frontend
npm ci --no-audit --no-fund
npm run check
npm run test:e2e
npm run test:cross-browser

# Documentation (from repository root)
Set-Location ..
python -m pip install -e ".[docs]"
python scripts/check_documentation.py
python -m mkdocs build --strict
```

The generated documentation is written to `site/`; it is a build artifact and must not be edited by hand.
