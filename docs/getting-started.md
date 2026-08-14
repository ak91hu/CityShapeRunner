# Developer quick start

This guide brings up the FastAPI service and Vite client locally, then verifies the street-routing contract with a real request.

## Prerequisites

| Tool | Supported baseline | Used for |
| --- | --- | --- |
| Python | 3.12 or newer; CI uses 3.14 | API, route pipeline, tests, MkDocs |
| Node.js | 24; CI uses Node 24 | React client, Vite, Playwright |
| npm | Version bundled with Node 24 | Reproducible install from `package-lock.json` |
| Git | Current supported version | Source and change review |
| Chromium | Installed by Playwright | Functional browser tests |

For usable route generation, also obtain an OpenRouteService API key. LLM credentials are optional because deterministic shape behavior remains available, but street routing is not optional for a GPX/TCX result.

## 1. Create the Python environment

=== "PowerShell"

    ```powershell
    py -3.14 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev,all,docs]"
    ```

=== "bash"

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev,all,docs]"
    ```

Extras are intentionally separated:

- `dev` installs pytest, Ruff, and mypy;
- `docs` installs the pinned MkDocs toolchain;
- `all` installs hosted OpenAI-compatible and Anthropic clients;
- `opencode`, `openai`, or `anthropic` can be installed alone for a smaller provider-specific environment.

## 2. Configure local services

```powershell
Copy-Item .env.example .env
```

At minimum, set:

```dotenv
ORS_API_KEY=your_openrouteservice_key
NOMINATIM_EMAIL=developer@example.com
```

To enable model-assisted shape generation, configure one provider as well:

```dotenv
LLM_PROVIDER=opencode
OPENCODE_API_KEY=your_server_side_key
LLM_MODEL=glm-5.2
```

Never put provider keys into `frontend/` or a `VITE_*` variable. Vite variables are compiled into browser assets and are public. See the [configuration reference](configuration-reference.md) for every setting and its precedence.

## 3. Start the API

```powershell
gps-art-wizzard
```

The default bind address is `http://127.0.0.1:8000`. Useful development endpoints:

- `GET http://127.0.0.1:8000/health` — lightweight liveness and gallery configuration;
- `GET http://127.0.0.1:8000/docs` — interactive Swagger UI generated from Pydantic models;
- `GET http://127.0.0.1:8000/openapi.json` — machine-readable OpenAPI schema.

## 4. Start the web client

Open a second shell:

```powershell
Set-Location frontend
npm ci --no-audit --no-fund
npm run dev
```

Visit `http://127.0.0.1:5173`. During development, Vite proxies `/health` and `/generate` to port `8000`. The production container instead serves the compiled SPA and API from the same FastAPI origin.

## 5. Exercise the API

Interpretation is fast and does not run the street-routing pipeline:

```powershell
$body = @{ prompt = "a heart run in Budapest, about 8 km" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/interpret `
  -ContentType application/json `
  -Body $body
```

Generate the route with the same payload:

```powershell
$result = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/generate `
  -ContentType application/json `
  -Body $body

$result.snapped
$result.distance_km
$result.route_verification
```

A successful exportable response must have a street-connected route. If ORS is unavailable or no connected route exists, expect HTTP `503` and no unsafe straight-line GPX.

## 6. Run the checks

```powershell
$env:GEOCODE_OFFLINE = "1"
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard
python -m pytest -q

Set-Location frontend
npm run build
npm run test:e2e

Set-Location ..
python -m mkdocs build --strict
```

`GEOCODE_OFFLINE=1` keeps automated tests deterministic and prevents tests from relying on Nominatim availability.

## Documentation authoring

```powershell
python -m mkdocs serve
```

Open `http://127.0.0.1:8000` unless port `8000` is already occupied by the API. To run both simultaneously:

```powershell
python -m mkdocs serve --dev-addr 127.0.0.1:8001
```

The CI build uses `python -m mkdocs build --strict`, so invalid configuration, unresolved internal links reported by MkDocs, and other documentation warnings fail the job.

## Common startup failures

| Symptom | Likely cause | Resolution |
| --- | --- | --- |
| `/generate` returns `503` | Missing/invalid ORS key, provider outage, or no connected route | Verify `ORS_API_KEY`, inspect correlated logs, retry a different placement; do not weaken fail-closed behavior |
| Address cannot be found | Incomplete address or Nominatim unavailable | Add city/country context or select a map point |
| Browser reports API unreachable | API is stopped or `VITE_API_BASE` points elsewhere | Check `/health`, CORS origins, and the frontend build-time base URL |
| Model provider is skipped | Key/model combination is not configured | Review provider-specific variables and `LLM_FALLBACK` |
| Docs build warns about a page | File is missing from navigation or contains a bad internal link | Update `mkdocs.yml` and use source-relative Markdown links |
| Playwright has no browser | Chromium dependencies were not installed | Run `npx playwright install --with-deps chromium` |
