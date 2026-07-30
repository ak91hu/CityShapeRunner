# Production deployment

The production image builds the React application in a disposable Node stage
and serves the resulting static assets from the same FastAPI process as the API.
Node, npm caches, source maps from development, test files, and Python build
tools are not copied into the runtime image.

## Build and run

```bash
docker build --tag gps-art-wizzard:0.1.0 .
docker run --rm --name gps-art-wizzard \
  --publish 8000:8000 \
  --env-file .env \
  --env API_HOST=0.0.0.0 \
  gps-art-wizzard:0.1.0
```

The default image contains no hosted-LLM SDK and uses deterministic planning
when no provider is available. Include the OpenAI-compatible SDK only for an
OpenCode or OpenAI deployment:

```bash
docker build --build-arg INSTALL_EXTRAS=opencode --tag gps-art-wizzard:0.1.0-opencode .
```

Use `INSTALL_EXTRAS=anthropic` for Anthropic or `INSTALL_EXTRAS=all` for both
hosted-provider SDKs. The local Ollama integration uses the base HTTP client and
does not require an additional Python SDK. Keeping the default image
provider-free reduces image size, installation time, and dependency count.
Set `OLLAMA_BASE_URL` only when an Ollama service is reachable from the
container; `localhost` refers to the container itself, not its host.

## Runtime contract

- Listen address: `0.0.0.0:8000` by default; override with `API_PORT`.
- Liveness/readiness endpoint: `GET /health`.
- Route generation endpoint: `POST /generate`.
- Static web client: `GET /` when the frontend build is present.
- Persistent storage: not required. Eligible GPX/TCX documents are returned in
  the API response and remain in memory by default. Configure `EXPORT_DIR` only
  when server-side copies are required.
- Network: outbound HTTPS is required for the configured geocoder, road router,
  and hosted LLM provider.
- Common supported-city/template requests need only the road router at
  generation time: intent, city lookup, planning, and refinement are local.
- Process model: one Uvicorn worker per container. Scale with additional
  containers only after measuring external API quotas and latency.

Start with one CPU and 512 MiB of memory, then measure with representative
shapes, distances, and concurrent requests. NumPy and Shapely trade a modest
baseline memory cost for substantially faster geometry operations. Platform
request timeouts should accommodate the configured external services and
refinement count.
The default budget is six refinement passes after the initial ORS candidate. Reduce
`MAX_REFINEMENT_ITERATIONS` only when API quota or latency is more important
than difficult-city shape fidelity.
Smart suggestions can measure up to three distinct city-specific shapes before
refinement. The search stops as soon as a road-routed candidate passes both the
recognisability and overall-quality gates, while explicit shape, letter, and
number requests never trigger cross-shape search.

## Required production settings

Inject secrets through the hosting platform; never bake `.env` into an image.
At minimum, configure:

```dotenv
ORS_API_KEY=...
ORS_CONTINUE_STRAIGHT=false
LLM_PROVIDER=opencode
OPENCODE_API_KEY=...
NOMINATIM_EMAIL=operations@example.com
WEB_CORS_ORIGINS=https://routes.example.com
API_HOST=0.0.0.0
# Structured rotating diagnostics:
LOG_FORMAT=json
LOG_FILE=/data/logs/gps-art-wizard.log
LOG_MAX_BYTES=5000000
LOG_BACKUP_COUNT=5
# Optional persistent server-side copies:
# EXPORT_DIR=/data/exports
```

Without `ORS_API_KEY`, the application deliberately returns a straight-line
fallback marked `snapped=false`; that output is not a usable street route.
It remains editable/exportable as a guide with a manual-review warning.
Road-matched candidates below the recommended score, fidelity, or distance
targets are also retained instead of deleted. Without an LLM key,
deterministic planning remains available; route refinement is always
deterministic and uses measured geometry.

When `EXPORT_DIR` or `LOG_FILE` uses persistent storage, mount a writable
volume at the configured path and grant it to container user `10001`. Do not
set `EXPORT_DIR` on stateless deployments; console JSON logging continues if a
file path is unavailable.

Restrict `WEB_CORS_ORIGINS` to trusted browser origins. Terminate TLS at the
hosting platform or reverse proxy, cap request-body size, and apply rate limits
to `/generate` because one request can fan out to several external calls.

## Health check

The image includes a dependency-free health check. An orchestrator can use the
same endpoint:

```text
GET /health
200 {"status":"ok","service":"GPS Art Wizard","version":"0.1.0"}
```

The endpoint verifies that the process can answer HTTP requests. It intentionally
does not call paid or rate-limited external services.

## Packaging note

Python wheels include the prompt templates from
`gps_art_wizzard/prompts/*.txt`. Agent skills are intentionally maintained as
project documentation under `docs/skill-*.md`, and the current skill loader
resolves them relative to a source checkout. A bare wheel installed outside the
repository therefore runs without those injected skill documents. The
production image avoids that degradation by copying both `docs/` and `config/`
into the runtime working directory.

## Upgrade policy

Direct Python dependencies are pinned to audited stable releases in
`pyproject.toml`. Re-audit release notes and run the full unit and browser test
suites before changing a pin. Frontend direct dependencies are exact pins in
`frontend/package.json`; npm currently resolves their transitive dependencies
at install time. Generate and commit a fresh lockfile in a network-enabled
release environment, then replace `npm install` with `npm ci` in the image and
CI to make the complete Node graph reproducible.
