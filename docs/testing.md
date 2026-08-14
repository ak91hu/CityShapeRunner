# Testing guide

The project has two complementary automated suites:

- Python unit and integration tests validate configuration, request contracts,
  geometry, route selection, provider fallback, export, gallery security,
  logging, and the complete offline planning pipeline.
- Playwright functional tests drive the React UI in desktop Chromium and a
  Pixel 7-sized mobile Chromium project. Network fixtures keep these tests
  repeatable and prevent calls to paid or rate-limited services.

## One-time setup

Install the backend development dependencies and frontend lockfile exactly:

```bash
python -m pip install -e ".[dev,all]"
cd frontend
npm ci
npx playwright install chromium
```

Node.js 24 and Python 3.12 or newer match the supported local and CI
environments.

## Run every check

From the repository root on Bash:

```bash
export GEOCODE_OFFLINE=1
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard
python -m pytest -q

cd frontend
npm run build
npm run test:e2e
```

The PowerShell equivalent is:

```powershell
$env:GEOCODE_OFFLINE = "1"
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard
python -m pytest -q

Set-Location frontend
npm run build
npm run test:e2e
```

`npm run test:e2e` starts a fresh Vite server on `127.0.0.1:4173`; do not start
that test server manually. The configuration uses one worker because Leaflet,
ResizeObserver teardown, and browser rendering are more stable when the two
browser projects execute serially.

### Browser tests and live services

The default Playwright run contains 87 logical browser tests. Each test runs in
desktop Chromium and a Pixel 7-sized Chromium project, so a complete run reports
174 executions.

These tests are deterministic functional UI tests, not live-service smoke tests.
They intercept the HTTP boundary for route generation, editing, acceptance, and
gallery operations. The gallery-publish scenarios render a real Leaflet map,
capture the PNG in the browser, submit the publish request through the UI, and
assert the exact payload and refreshed gallery state, but the request is fulfilled
by Playwright. Therefore a successful default run does **not** create a Cloudinary
asset, consume routing/model-provider quota, or require service credentials.

Keep live Cloudinary checks separate from the default suite: they create external
state, depend on credentials and network availability, and can be flaky or costly.
The current local environment must provide all Cloudinary and gallery-signing
settings before a live smoke test can be run; the deterministic suite must never
silently fall through to those services.

On a restricted Windows profile, pytest may be unable to create its normal
directory under `%TEMP%`. The project configuration already uses the ignored,
workspace-local `.pytest-tmp` directory, so the ordinary command works:

```powershell
python -m pytest -q
```

Pytest owns and may clear `.pytest-tmp`; do not use the repository root or a
shared folder as its base directory.

## Run focused tests

Backend examples:

```bash
python -m pytest -q tests/test_api_contracts.py
python -m pytest -q tests/test_config.py
python -m pytest -q tests/test_route_engine.py -k preflight
python -m pytest -q tests/test_api_contracts.py tests/test_logging.py tests/test_route_engine.py -k "unrouted or unsafe_gpx or remaining_preflight"
```

Frontend examples from `frontend/`:

```bash
npx playwright test tests/workflows.spec.js --project=chromium
npx playwright test tests/app.spec.js --grep "API failures show|straight-line preview"
npx playwright test --grep "gallery"
npm run test:e2e:ui
```

Use the Chromium-only command for a quick development loop, then run
`npm run test:e2e` before handing off a change so the mobile project is also
covered.

## Coverage map

| Area | Primary tests |
|---|---|
| Configuration, current HeiGIT ORS endpoint, legacy-host compatibility, and provider selection | `tests/test_config.py`, `tests/test_route_engine.py` |
| FastAPI validation, fail-closed generation/editing, and safe errors | `tests/test_api_contracts.py`, `tests/test_logging.py` |
| Shape catalog, complete 145-template recommendation profiling, bounded ranking cache, unexpected-value normalization, all 230 unique destination contexts (including 45 explicit Balaton route priors), geometry, routing, quality, and export | `tests/test_route_engine.py`, `tests/test_pipeline.py` |
| Gallery tokens, PNG safety, and Cloudinary boundaries | `tests/test_gallery.py` |
| Skill discovery and prompt injection | `tests/test_skills.py` |
| Main route creation, structured-action placement, animated/cancellable waiting state, fail-closed straight-line previews, and responsive result UI | `frontend/tests/app.spec.js` |
| Validation, activity limits, cancellation, reduced-motion waiting, keyboard flow, candidate switching, edit/export safety, reviewed-route telemetry resilience, GPX/TCX downloads, and gallery failure/pagination/removal | `frontend/tests/workflows.spec.js` |
| Planner navigation, shared header/favicon identity, meaningful visual/DOM/focus order, 44-pixel target floor, plain-language content hierarchy, removal of decorative UI patterns, atomic validation states, searchable 158-option catalog, and grouped 230-destination structured suggestions | `frontend/tests/planner-functional.spec.js` |
| Result focus, route options, metrics, verification, route facts, history, and audit disclosures | `frontend/tests/results-functional.spec.js` |
| Keyboard editing, closed-loop synchronization, reset/busy states, edited routes, and scoped approval | `frontend/tests/editor-export-functional.spec.js` |
| Gallery empty/error/configuration states, pagination, ownership/removal, consent, PNG capture, and mocked publishing | `frontend/tests/gallery-resilience-functional.spec.js` |

The browser tests mock `/generate`, `/edit-route`, `/route-acceptance`, and
gallery endpoints at the HTTP boundary. This makes them functional UI tests,
not live-provider smoke tests. The Python offline pipeline tests cover the
backend orchestration behind those mocked responses.

The safety regression has three independent assertions:

1. the orchestrator tries later preflight-ranked placements when the first
   Directions candidate is not connected;
2. `/generate` and `/edit-route` return HTTP 503 instead of exposing an
   unrouted GPX/TCX;
3. the browser hides approval and download actions even if a malformed mocked
   response claims `snapped=false` while still containing GPX text.

These deterministic tests do not prove that a deployed ORS key, quota, DNS,
or outbound network is healthy. A production smoke test must use a harmless
representative request, expect HTTP 200 with `snapped=true`, and inspect the
returned street polyline. HTTP 503 is the expected safe behaviour when no
connected route can be obtained.

## Playwright failures

The test runner writes failure screenshots, error context, and retry traces
under `frontend/test-results/`. CI also produces an HTML report. Start with the
first failed assertion: later connection failures usually indicate that the
local Vite test server exited, while a locator failure with a rendered page is
normally a UI contract regression.

For interactive debugging, run `npm run test:e2e:ui`. Keep locators based on
roles, labels, and user-visible names; use CSS selectors only for visual details
that do not have an accessibility role, such as Leaflet markers or metric-card
internals.
