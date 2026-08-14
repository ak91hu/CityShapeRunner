# Configuration reference

Configuration is loaded when the Python process imports the application. Local `.env` values are loaded by `python-dotenv`; deployment platforms normally inject the same names as environment variables.

## Precedence and lifecycle

For workflow and routing settings, effective values follow this precedence:

1. environment variable or `.env` value;
2. matching `config/settings.yaml` overlay;
3. hard-coded dataclass default in `gps_art_wizzard/config.py`.

The YAML loader currently applies only the `workflow` and `routing` sections. Provider, geocoder, server, export, gallery, and logging values are environment-driven. `get_settings()` is cached, so tests that modify configuration after first access must clear the cache; production changes require a process restart.

!!! note

    Defaults below describe the checked-in application, including `config/settings.yaml`. A hosting environment may override them.

## LLM providers

At least one LLM provider improves custom free-text drawing and semantic verification. The route pipeline retains deterministic behavior without a hosted model, but cannot create a usable GPS export without street routing.

| Variable | Repository default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `auto` in code; example uses `opencode` | Primary provider: `opencode`, `openai`, `anthropic`, `ollama`, or automatic selection |
| `LLM_FALLBACK` | `opencode,anthropic,openai,ollama` | Comma-separated fallback sequence |
| `LLM_MODEL` | empty | General model ID when no provider-specific model is set |
| `OPENCODE_MODEL` | empty | OpenCode model override |
| `OPENAI_MODEL` | empty | OpenAI model override |
| `ANTHROPIC_MODEL` | empty | Anthropic model override |
| `OLLAMA_MODEL` | empty | Ollama model override |
| `OPENCODE_STRUCTURED_MODEL` | `gpt-5.4-mini` | Model used for strict-schema jobs through the OpenCode-compatible Responses endpoint |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `LLM_MAX_TOKENS` | `2048` | Provider output-token budget |
| `OPENCODE_API_KEY` | empty | Server-side OpenCode credential |
| `OPENAI_API_KEY` | empty | Server-side OpenAI credential |
| `ANTHROPIC_API_KEY` | empty | Server-side Anthropic credential |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1` | OpenAI-compatible OpenCode base URL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` in code | Local Ollama endpoint; production image explicitly clears it unless configured |

Provider-specific model IDs take precedence over `LLM_MODEL` for their provider. This prevents a fallback provider from receiving another provider's incompatible model name.

## Street routing

| Variable | Effective default | Description |
| --- | --- | --- |
| `ORS_API_KEY` | empty | OpenRouteService credential; required for selectable routes and GPX/TCX output |
| `ORS_BASE_URL` | `https://api.heigit.org/openrouteservice` | ORS API root |
| `ORS_SNAP_RADIUS_M` | `120` | Maximum matching radius for guide points |
| `ORS_CONTINUE_STRAIGHT` | `false` | Whether intermediate points forbid U-turns; GPS-art cusps generally require `false` |
| `ORS_PREFERENCE` | `shortest` from YAML | Routing preference; supported values depend on ORS, normally `recommended` or `shortest` |

Do not increase `ORS_SNAP_RADIUS_M` merely to make a failing route succeed. A large radius can move strokes far from the intended drawing. The preflight stage exists to search better placements before spending full Directions calls.

## Geocoding

| Variable | Default | Description |
| --- | --- | --- |
| `NOMINATIM_BASE_URL` | `https://nominatim.openstreetmap.org` | Nominatim endpoint |
| `NOMINATIM_EMAIL` | empty | Contact email sent for responsible public-service usage |
| `GEOCODE_OFFLINE` | unset | Any non-empty value enables deterministic/offline geocoding behavior used by automated tests |

`GEOCODE_OFFLINE` is a test/development switch, not a production substitute for resolving arbitrary addresses and cities.

## Workflow and quality

| Variable | Effective default | Description |
| --- | --- | --- |
| `MAX_REFINEMENT_ITERATIONS` | `8` | Upper bound for route refinement passes |
| `VALIDATION_SCORE_THRESHOLD` | `0.72` | Composite quality threshold |
| `DEFAULT_SPORT` | `run` | Sport applied when the prompt omits it |
| `DEFAULT_CITY` | `Budapest` | City applied when the prompt omits it |
| `DEFAULT_RUN_DISTANCE_KM` | `8` | Default run distance |
| `DEFAULT_BIKE_DISTANCE_KM` | `20` | Default bike distance |
| `PREFLIGHT_ENABLED` | `true` | Enables coarse-to-fine street-fit search |
| `PREFLIGHT_MAX_PLACEMENTS` | `180` | Cheap placement transformations examined before full routing |
| `PREFLIGHT_SHORTLIST` | `7` | Top placements advanced to expensive routing |
| `PREFLIGHT_GUIDE_POINTS` | `18` | Sample count used for preflight snapping |
| `AI_SHAPE_VERIFIER_ENABLED` | `true` | Enables rendered semantic review for free-text shapes |
| `AI_SHAPE_MIN_SEMANTIC_SCORE` | `0.68` | Minimum semantic cue score |
| `AI_SHAPE_MAX_CANDIDATES` | `4` | Maximum generated drawing alternatives |

The YAML file also defines sport bounds (`run: 3–60 km`, `bike: 10–200 km`) and `min_shape_fidelity: 0.7`; these currently have no direct environment-variable counterpart.

Performance tuning must preserve the routing and quality contract. Reducing `PREFLIGHT_MAX_PLACEMENTS`, `PREFLIGHT_SHORTLIST`, candidate count, or refinement iterations saves upstream calls but reduces search breadth. Benchmark representative cities and inspect fidelity, distance fit, closure, connected geometry, and failure rate before deploying a change.

## API server and browser origin

| Variable | Default | Description |
| --- | --- | --- |
| `API_HOST` | `127.0.0.1` locally; image sets `0.0.0.0` | Uvicorn bind host |
| `API_PORT` | `8000` | Uvicorn port when `PORT` is absent |
| `PORT` | unset | Hosting-platform port; takes precedence over `API_PORT` |
| `WEB_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact allowed origins |
| `VITE_API_BASE` | empty/same origin | Frontend compile-time API base, without a trailing slash |

`VITE_API_BASE` is read during the frontend build. Never place secrets in it or any other `VITE_*` value. In the production container the recommended value is empty because FastAPI serves the SPA and API from one origin.

## Runtime identity and structured logging

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `local`; image sets `production` | Environment label and local-file logging behavior |
| `SERVICE_NAME` | `gps-art-wizard` | Structured log service label; falls back to platform `K_SERVICE` |
| `APP_REVISION` | empty | Release/commit identifier; falls back to `K_REVISION` |
| `LOG_LEVEL` | `INFO` | Python root log level |
| `LOG_FORMAT` | `json` | `json` for structured JSONL; any other value selects readable text |
| `LOG_FILE` | `logs/gps-art-wizard.log` locally, empty in production | Optional rotating local log file; console output always remains |
| `LOG_MAX_BYTES` | `5000000` | Rotation threshold, clamped to at least 64,000 bytes |
| `LOG_BACKUP_COUNT` | `5` | Rotated files retained, clamped to at least one |

Structured records contain service/environment, timestamp, severity, logger, request ID, message, and event-specific fields. Secrets and full route geometry are intentionally excluded. See [Production deployment](deployment.md#persistent-and-searchable-grafana-cloud-logs) for the Northflank-to-Grafana path.

## Export and gallery

| Variable | Default | Description |
| --- | --- | --- |
| `EXPORT_DIR` | empty | Optional directory for persisted selected exports; empty keeps responses stateless/in-memory |
| `CLOUDINARY_URL` | empty | Server-only `cloudinary://API_KEY:API_SECRET@CLOUD_NAME` credential for the anonymous screenshot gallery |

The gallery stores rendered map images, not GPX/TCX tracks. Publishing requires both an explicit public-location confirmation and a short-lived server-issued capability token. Deletion requires the returned removal token.

## Production minimum

```dotenv
APP_ENV=production
SERVICE_NAME=gps-art-wizard
LOG_FORMAT=json
LOG_FILE=
API_HOST=0.0.0.0
ORS_API_KEY=<secret>
NOMINATIM_EMAIL=operations@example.com
WEB_CORS_ORIGINS=https://your-public-service.example
```

Add one LLM provider credential/model if model-assisted shapes are required, and `CLOUDINARY_URL` only if the public screenshot gallery is enabled.

## Secret-handling rules

- Commit `.env.example`, never `.env`.
- Configure `*_API_KEY` and `CLOUDINARY_URL` in the hosting platform's secret store.
- Keep secrets out of Vite variables, browser logs, map metadata, GPX/TCX names, screenshots, and documentation examples.
- Rotate a key immediately if it appears in Git history or CI logs; removing the current file is not sufficient.
- Treat gallery publish/removal tokens as capabilities even though they are short-lived or asset-specific.
