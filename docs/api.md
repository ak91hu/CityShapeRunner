# API reference

Base URL: `http://localhost:8000`

All endpoints return JSON. The API is self-documented via OpenAPI at `/docs`.

## Health

```
GET /api/health
```

```json
{ "status": "ok", "version": "1.0.0", "db": false }
```

## Cities

```
GET /api/cities
```

Returns all cities with road network metadata.

```
GET /api/cities/{city_id}
```

Returns a single city with details.

```
GET /api/cities/{city_id}/artworks?activity=&difficulty=
```

Returns artworks compatible with the given city, including fit scores and
distance ranges. Filters: `activity` (running, cycling, walking) and
`difficulty` (easy, medium, hard).

## Artworks / Shapes

```
GET /api/artworks
```

Returns all 150+ artworks with metadata (category, complexity, tags, SVG
preview URL).

```
GET /api/artworks/{artwork_id}
```

Returns a single artwork with full metadata and city affinities.

```
GET /api/artworks/{artwork_id}/cities?activity=&distance_km=
```

Returns cities compatible with the given artwork. Query params:
- `activity` (running, cycling, walking) — default: running
- `distance_km` (float) — optional, filters to compatible distance range

## Generation

```
POST /api/generation/generate
```

```json
{
  "city_id": "budapest",
  "artwork_id": "heart",
  "activity": "running",
  "distance_km": 8.0
}
```

Returns a job ID:

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

```
GET /api/generation/jobs/{job_id}
```

Returns the job status and (when completed) the results:

```json
{
  "status": "completed",
  "results": {
    "candidates": [
      {
        "id": "candidate-uuid",
        "score_shape": 0.85,
        "score_road": 0.82,
        "score_dist": 0.91,
        "score_continuity": 0.88,
        "composite_score": 0.86,
        "distance_km": 8.1,
        "elevation_gain_m": 95,
        "track_points": 342,
        "summary": "Excellent shape fidelity with good road alignment",
        "rotation_deg": 15.0,
        "scale": 0.042
      }
    ]
  }
}
```

```
GET /api/generation/jobs/{job_id}/candidates/{candidate_id}/gpx?mode=continuous
```

Downloads a GPX 1.1 file. Mode: `continuous` (dense trackpoints) or `dots`
(key points only).

```
GET /api/generation/jobs/{job_id}/candidates/{candidate_id}/map
```

Returns GeoJSON for the candidate route — used by the frontend map.

## Routes (persisted)

```
GET /api/routes/{route_id}
```

Returns a generated route by ID.

```
GET /api/routes/{route_id}/gpx?mode=continuous
```

Downloads GPX for a persisted route.

```
GET /api/routes/{route_id}/map
```

Returns GeoJSON for a persisted route.

## Sharing

```
POST /api/shares
```

```json
{
  "route_id": "uuid"
}
```

Creates a shareable link. Returns a short code.

```
GET /api/shares/{short_code}
```

Resolves a share code to the route.

## Generation stages

The worker reports its progress through these stages:

| Stage | Description |
|---|---|
| loading_city | Loading city metadata |
| loading_road_graph | Loading streets & paths |
| building_indexes | Building road network indexes |
| parsing_shapes | Processing SVG shapes |
| ranking_shapes | Ranking shapes for the city |
| selecting_artworks | Selecting matching shapes |
| generating_placements | Generating candidate placements |
| generating_transforms | Testing scale/rotation combinations |
| corridor_scoring | Quick reject bad placements |
| fitting_candidates | Detailed size/rotation testing |
| beam_matching | Matching to road graph |
| constructing_routes | Building continuous routes |
| repairing_routes | Connecting disconnected segments |
| refining_candidates | Optimizing top candidates |
| scoring | Scoring each candidate |
| storing_results | Persisting and snapping results |
| ai_retry | AI-assisted retry (if needed) |
| completed | Done |
