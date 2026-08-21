# HTTP API reference

The public service is a FastAPI application. Pydantic validates all JSON request bodies before route logic runs. The runtime publishes the authoritative, version-matched OpenAPI schema at `/openapi.json` and interactive Swagger UI at `/docs`.

This page describes the API exposed **by** GPS Art Wizard. For the services called **by the backend**—ORS, Nominatim, model providers, Cloudinary, Open-Meteo, and remote image hosts—see [External API integrations](external-apis.md).

## Cross-cutting behavior

### Base URL and content type

Local examples use `http://127.0.0.1:8000`. JSON endpoints expect `Content-Type: application/json` and return JSON. GPX/TCX exports are returned as strings inside successful JSON responses, not as separate download endpoints.

### Request correlation

Every HTTP response contains `X-Request-ID`. A caller may supply `X-Request-ID` when it contains at most 80 characters from `A-Z`, `a-z`, `0-9`, `.`, `_`, `:`, or `-`; otherwise the service generates a UUID. The same value is attached to structured logs and appears as `request_id` in main route responses.

### Standard error shape

FastAPI errors use:

```json
{
  "detail": "Human-readable explanation"
}
```

| Status | Meaning in this service |
| --- | --- |
| `409` | A state transition is invalid, for example accepting a route that is not street-routed |
| `422` | Pydantic validation failed, the prompt/reference/address is invalid, or domain input cannot be processed |
| `500` | Internal interpretation, generation, validation, or export failed |
| `502` | An optional upstream gallery service failed unexpectedly |
| `503` | Required routing/gallery configuration is missing or connected street routing is unavailable |

!!! warning "Safety boundary"

    Treat `503` from `/generate` or `/edit-route` as a hard failure. The service intentionally withholds GPX/TCX rather than returning straight segments across non-routable space.

## Endpoint summary

| Method | Path | Purpose | Main success |
| --- | --- | --- | --- |
| `GET` | `/health` | Liveness and optional gallery state | `200` |
| `POST` | `/interpret` | Preview the exact intent model used by generation | `200` |
| `POST` | `/generate` | Generate, route, score, and export candidate routes | `200` |
| `POST` | `/edit-route` | Re-route user control points and rebuild exports | `200` |
| `POST` | `/route-acceptance` | Audit an explicit user decision without storing geometry | `200` |
| `GET` | `/gallery` | List anonymous public map screenshots | `200` |
| `POST` | `/gallery` | Publish a confirmed screenshot | `200` |
| `POST` | `/gallery/delete` | Remove a published screenshot with its removal token | `200` |
| `POST` | `/mural-plan` | Split a route by distance across participants | `200` |
| `POST` | `/timed-readiness` | Evaluate time-aware readiness at a location | `200` |
| `POST` | `/inkproof-analysis` | Estimate whether GPS drift erases fine details | `200` |
| `POST` | `/art-rescue` | Compare recorded GPX sessions with planned ink | `200` |
| `POST` | `/recognition-repair` | Re-route from the strongest visual landmarks | `200` |

## Health

### `GET /health`

This endpoint does not call external routing or model providers.

```json
{
  "status": "ok",
  "service": "GPS Art Wizard",
  "version": "0.1.0",
  "gallery": { "configured": false }
}
```

Use it for container liveness. It proves the process can serve HTTP, not that ORS, LLM, Nominatim, or Cloudinary is healthy.

## Interpret a route idea

### `POST /interpret`

Uses the same `GenerateRequest` input and `IntentAgent` as `/generate`, but stops before placement and routing. It is designed for a low-cost confirmation step in the UI.

```json
{
  "prompt": "a heart run in Budapest, about 8 km",
  "start_address": "Heroes' Square, Budapest",
  "route_preferences": {
    "avoid_steps": true,
    "avoid_ferries": true,
    "avoid_fords": true,
    "prefer_quiet": false,
    "prefer_green": true
  }
}
```

The response includes normalized intent, `drawing_kind` (`template`, `custom`, `text`, or `suggestion`), applied defaults, confidence values, and any clarifications.

## Generate a street route

### `POST /generate`

#### Request

| Field | Type | Rules | Default |
| --- | --- | --- | --- |
| `prompt` | string | Required, 1–320 normalized characters, must contain an alphanumeric character | — |
| `intent_override` | object/null | Confirmed `shape`, `text`, `city`, `sport`, `distance_km`, `style`, or `suggest` correction | `null` |
| `start_point` | object/null | `latitude`, `longitude`, optional `label`; mutually exclusive with `start_address` | `null` |
| `start_address` | string/null | At most 180 characters; geocoded before generation | `null` |
| `start_direction_deg` | number/null | `0 <= value < 360` | `null` |
| `route_preferences` | object | Five booleans described below | all `false` |
| `reference_image_url` | HTTP(S) URL/null | Public image, at most 2,048 characters | `null` |

`intent_override.sport` is `run` or `bike`; `distance_km` is greater than zero and at most 500. `route_preferences` supports `avoid_steps`, `avoid_ferries`, `avoid_fords`, `prefer_quiet`, and `prefer_green`.

Example with a fixed start point:

```json
{
  "prompt": "draw the letter A by bike in Szeged, 18 km",
  "start_point": {
    "latitude": 46.253,
    "longitude": 20.1414,
    "label": "Selected meeting point"
  },
  "start_direction_deg": 90,
  "route_preferences": {
    "avoid_steps": true,
    "avoid_ferries": true,
    "avoid_fords": true,
    "prefer_quiet": true,
    "prefer_green": false
  }
}
```

#### Response groups

The response is intentionally rich because the client must explain and compare route quality:

| Group | Important fields | Meaning |
| --- | --- | --- |
| Identity | `request_id`, `prompt`, `intent` | Correlation and normalized request |
| Workflow | `workflow` | Run ID/status/mode, duration, limits, step attempts, AI/fallback counters, and safe reason codes |
| Drawing | `shape`, `requested_shape`, `suggested_shape`, `fit_decision` | Selected contour and any substitution decision |
| Result | `distance_km`, `snapped`, `points_preview`, `ideal_preview`, `landmark_preview` | Routable geometry and reference geometry |
| Quality | `validation`, `route_verification`, `route_details`, `below_threshold` | Similarity, distance, closure, readiness, quality gates |
| Alternatives | `candidates`, `candidate_audit`, `candidate_summary`, `preflight_candidates`, `street_canvas` | Ranked street-routed candidates and placement evidence |
| Pipeline | `iterations`, `candidate_count`, `preflight_count`, `history`, `errors` | Generation/refinement trace |
| Export | `gpx`, `tcx`, `file_paths` | In-memory documents and optional persisted paths |
| Gallery | `gallery_publish_token` | Short-lived capability for publishing the rendered map, when configured |

Preview arrays are sampled for browser rendering and must not be treated as the complete export geometry. Use the returned GPX/TCX content for activity devices.

The `workflow` summary is operational metadata, not hidden model reasoning. It
does not contain prompts, raw model responses, exception messages, detailed
lifecycle events, or route geometry. `status=needs_review` describes the quality
outcome; `mode=deterministic` can also be the intentional fast path for a known
template or text shape.

## Edit a route

### `POST /edit-route`

The editor sends geographic control points. The server must route them through ORS again; it never trusts the browser polyline as an exportable route.

```json
{
  "control_points": [[47.4979, 19.0402], [47.501, 19.052], [47.493, 19.057]],
  "reference_points": [[47.4979, 19.0402], [47.503, 19.05], [47.493, 19.057]],
  "sport": "run",
  "closed": false,
  "target_distance_km": 8,
  "name": "Edited heart",
  "shape_name": "heart",
  "route_preferences": {
    "avoid_steps": false,
    "avoid_ferries": true,
    "avoid_fords": true,
    "prefer_quiet": true,
    "prefer_green": false
  }
}
```

Constraints:

- `control_points`: 2–200 valid `[latitude, longitude]` pairs;
- `reference_points`: 0–500 pairs; when absent, control points are the similarity reference;
- names are non-blank and limited to 120/80 characters;
- `target_distance_km`, when present, is greater than zero and at most 500.

The response contains street-routed `points_preview`, distance, validation, verification, route details, GPX, optional TCX, and warnings. A routing mismatch is `503`; validation/export failures are `500`.

## Record explicit acceptance

### `POST /route-acceptance`

Records structured decision metadata in logs without retaining route geometry.

```json
{
  "generation_request_id": "request-id-from-generate",
  "route_id": "candidate-2",
  "shape_name": "heart",
  "automatic_checks_passed": false,
  "snapped": true,
  "failed_gates": ["shape fidelity"],
  "score": 0.78,
  "shape_fidelity": 0.68,
  "distance_km": 8.31
}
```

If `snapped` is false, the endpoint returns `409`. A successful response is `{"recorded": true}`.

## Anonymous screenshot gallery

### `GET /gallery`

Query parameters: `limit` is 1–50 (default 24), `cursor` is an optional opaque string. An unconfigured gallery is a normal `200` response:

```json
{"configured": false, "assets": [], "next_cursor": null}
```

### `POST /gallery`

Requires `image_data_url` (100–8,000,000 characters), a server-issued `publish_token` (20–500 characters), and `confirm_public_location: true`. The confirmation is enforced by Pydantic.

### `POST /gallery/delete`

Requires a `public_id` matching `gps-art-gallery/<32 lowercase hex characters>` and the 64-character `removal_token` returned at publication. Configuration/token/image failures map to `503`, `403`, and `422`; unexpected Cloudinary failures map to `502`.

## GPS Art Intelligence endpoints

### `POST /mural-plan`

Splits 4–2,000 points by traveled distance among 2–24 participants. Accepts `name` and `sport`; returns per-participant previews, distances, and GPX. A route too short to produce all sections returns `422`.

### `POST /timed-readiness`

Accepts `latitude`, `longitude`, and ISO-8601 `departure_at`. A timestamp without a timezone is interpreted as UTC. Returns the readiness analysis from `tools/timed_readiness.py`.

### `POST /inkproof-analysis`

Accepts 4–5,000 points and `accuracy_m` from 3 to 50 (default 10). It estimates whether realistic GPS noise can erase route details.

### `POST /art-rescue`

Accepts 4–5,000 planned points, 1–12 named GPX recordings (each at most 2,000,000 characters), tolerance 5–100 metres, name, and sport. Malformed GPX/domain data returns `422`.

### `POST /recognition-repair`

Accepts 4–500 reference points, sport, closure flag, name, and route preferences. It extracts salient visual landmarks, street-routes those anchors, and returns the repaired preview, guide points, distance, recognition score, readiness, and GPX.

## Compatibility guidance

- Generate clients from `/openapi.json` for exact schema details, but preserve unknown response fields for forward compatibility.
- Do not equate HTTP `200` with field readiness: inspect `route_verification`, `below_threshold`, and readiness warnings.
- Do not construct routes from `ideal_preview` or browser-edited lines. Only server-returned street-routed exports are eligible for use.
- Log the response `X-Request-ID` with client-side errors; it is the primary join key for production diagnosis.
