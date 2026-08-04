# Production deployment

The production image builds the React application in a disposable Node stage
and serves the resulting static assets from the same FastAPI process as the API.
Node, npm caches, source maps from development, test files, and Python build
tools are not copied into the runtime image.

## Northflank Developer Sandbox

The repository is prepared for a
[Northflank combined service](https://northflank.com/docs/v1/application/getting-started/build-and-deploy-your-code).
The service builds the root `Dockerfile`, runs the React SPA and FastAPI API in
one container, exposes one HTTPS address on Northflank's `code.run` domain, and
automatically builds and deploys new commits from the linked branch.

Northflank's Developer Sandbox currently provides limited always-on services
without the sleep cycle used by many free web-service plans. It is intended for
hobby, preview, and testing workloads rather than production use and carries no
production SLA. The application's bounded but CPU-heavy geometry search should
therefore be measured after deployment before increasing external API usage.

### Create the service from the existing project

Inside the Northflank project:

1. Select **Create new → Service → Combined service**.
2. Use service name `gps-art-wizard`.
3. Link `ak91hu/CityShapeRunner`, branch `master`.
4. Select **Dockerfile** with build context `/` and path `/Dockerfile`.
5. Do not add a build command or command override. The image's default command
   is `gps-art-wizzard`.
6. Under **Networking**, expose container port `8000` as public HTTP. The
   Dockerfile already declares `EXPOSE 8000`; ensure the detected port is
   publicly exposed.
7. Under **Health checks**, use HTTP `GET /health` on port `8000`, with an
   initial delay of at least 20 seconds, a 30-second interval, and a 5-second
   timeout.
8. Select one free Sandbox instance and create the service.

The final public URL is displayed in the service header and ends in
`.code.run`. The application also accepts a platform-provided `PORT` variable
if Northflank supplies one; otherwise it listens on `0.0.0.0:8000`.

The standard Docker build includes the OpenCode/OpenAI-compatible SDK because
OpenCode is the default hosted LLM provider. Set the Docker build argument
`INSTALL_EXTRAS=all` only when Anthropic support is also required. Use an empty
`INSTALL_EXTRAS` value for a smaller deterministic-only image.

### Runtime variables and secrets

Add the following non-secret runtime variables to the combined service:

```dotenv
APP_ENV=production
SERVICE_NAME=gps-art-wizard
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=
EXPORT_DIR=
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
LLM_PROVIDER=opencode
LLM_FALLBACK=opencode
NOMINATIM_EMAIL=operations@example.com
ORS_CONTINUE_STRAIGHT=false
ORS_PREFERENCE=shortest
```

Replace `NOMINATIM_EMAIL` with a monitored contact address. `LOG_FILE` and
`EXPORT_DIR` must remain empty because the Sandbox container filesystem is not
the source of truth. GPX/TCX documents are generated in memory and downloaded
by the browser. `CLOUDINARY_URL` is optional; set it as a masked runtime secret
to enable the anonymous map-screenshot gallery. Never expose it to Vite or any
`VITE_*` variable.

Create a Northflank secret group or enter masked runtime secrets for:

```dotenv
ORS_API_KEY=...
OPENCODE_API_KEY=...
```

Never paste these keys into repository files, Docker build arguments, or public
logs. Without `ORS_API_KEY`, the app still starts but can only produce
straight-line manual-review guides. Without the optional LLM key, deterministic
planning remains available.

The SPA and API share one origin, so no production CORS entry is required.
Only set `WEB_CORS_ORIGINS` if a separate frontend domain must call the API; in
that case use the exact HTTPS origin rather than `*`.

### Persistent and searchable Grafana Cloud logs

The production image emits one-line structured JSON to stderr. Northflank
captures that stream and can forward it through its
[native Loki log sink](https://northflank.com/docs/v1/application/observe/configure-log-sinks),
so Grafana credentials do not enter the application container and HTTP log
delivery cannot delay route generation.

Configure the sink once at the Northflank account/team level:

1. In Grafana Cloud, create an access policy with **logs:write only**, then
   create and securely save its token.
2. Open the Grafana Cloud stack's Loki details and copy its URL and username.
3. In Northflank, open **Integrations → Log sinks → Add log sink → Loki**.
4. Enter the Grafana Loki URL and username; use the access-policy token as the
   password.
5. Select **JSON** encoding and restrict the sink to this Northflank project.
6. Save the sink. Northflank sends a validation entry before enabling it.

In Grafana, open **Explore**, select the Loki data source, and begin with:

```logql
{host="Northflank"} |= "gps-art-wizard"
```

Search a user-visible request identifier or an event without promoting those
high-cardinality values to Loki labels:

```logql
{host="Northflank"} |= "\"request_id\":\"debug-session-123\""
{host="Northflank"} |= "\"event\":\"generation.completed\""
{host="Northflank"} |= "\"severity\":\"ERROR\""
```

If the selected sink encoding exposes the application JSON directly, Grafana's
query-time JSON parser can also be used:

```logql
{host="Northflank"} | json | request_id="debug-session-123"
```

Keep `service`, `environment`, and bounded severity values as stream metadata;
keep `request_id`, prompts, route coordinates, and other unbounded/user values
out of labels. The application deliberately excludes API keys and prompt text,
but operational logs can still contain provider failures or route diagnostics.
Do not expose logs through a public application endpoint.

Locally, rotating JSONL files remain searchable without Grafana:

```powershell
Select-String -Path "logs\gps-art-wizard.log*" -Pattern '"request_id":"debug-session-123"'
Select-String -Path "logs\gps-art-wizard.log*" -Pattern '"event":"generation.completed"'
```

## Build and run

```bash
docker build --tag gps-art-wizzard:0.1.0 .
docker run --rm --name gps-art-wizzard \
  --publish 8000:8000 \
  --env-file .env \
  --env API_HOST=0.0.0.0 \
  gps-art-wizzard:0.1.0
```

The default image contains the OpenAI-compatible SDK used by the default
OpenCode provider. Build a smaller deterministic-only image by overriding the
default build argument with an empty value:

```bash
docker build --build-arg INSTALL_EXTRAS= --tag gps-art-wizzard:0.1.0-deterministic .
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
- Anonymous gallery endpoints: `GET /gallery`, `POST /gallery`, and
  `POST /gallery/delete` when `CLOUDINARY_URL` is configured.
- Static web client: `GET /` when the frontend build is present.
- Persistent filesystem storage: not required. Eligible GPX/TCX documents are
  returned in the API response and remain in memory by default. Configure
  `EXPORT_DIR` only when server-side copies are required. Gallery PNGs are
  stored directly in Cloudinary and indexed through its asset-search API.
- Logging: structured JSON is emitted to stderr. On Northflank, leave
  `LOG_FILE` empty and use a project-restricted Loki log sink for retention.
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
The default budget is eight refinement passes after the initial ORS candidate.
Reduce `MAX_REFINEMENT_ITERATIONS` only when API quota or latency is more
important than difficult-city shape fidelity.
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
# Structured diagnostics for a platform log sink:
APP_ENV=production
SERVICE_NAME=gps-art-wizard
APP_REVISION=
LOG_FORMAT=json
LOG_FILE=
# Optional persistent server-side copies:
# EXPORT_DIR=/data/exports
# Optional anonymous public map gallery (server secret only):
# CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

Without `ORS_API_KEY`, the application deliberately returns a straight-line
fallback marked `snapped=false`; that output is not a usable street route.
It remains editable and carries a prominent obstacle/manual-review warning;
the user must explicitly accept it before downloading its GPX.
Road-matched candidates below the recommended score, fidelity, or distance
targets are also retained instead of deleted. Without an LLM key,
deterministic planning remains available; route refinement is always
deterministic and uses measured geometry.

For a VM or paid container platform with an attached volume, set
`LOG_FILE=/data/logs/gps-art-wizard.log`, tune `LOG_MAX_BYTES` and
`LOG_BACKUP_COUNT`, mount `/data`, and grant it to container user `10001`.
Do not set `LOG_FILE` or `EXPORT_DIR` on stateless deployments; console JSON
logging remains authoritative there.

Restrict `WEB_CORS_ORIGINS` to trusted browser origins. Terminate TLS at the
hosting platform or reverse proxy, cap request-body size, and apply rate limits
to `/generate` because one request can fan out to several external calls.

## Health check

The image includes a dependency-free health check. An orchestrator can use the
same endpoint:

```text
GET /health
200 {"status":"ok","service":"GPS Art Wizard","version":"0.1.0","gallery":{"configured":false}}
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
`frontend/package.json`, while `frontend/package-lock.json` pins the transitive
graph. The production image uses `npm ci`; update and commit both files
together whenever frontend dependencies change.
