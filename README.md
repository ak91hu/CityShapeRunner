# CityShapeRunner

**SVG-first GPS art generation platform** — pick a shape and a city, and get a
GPX route that follows real streets while tracing that shape. Load it onto your
Garmin, Strava, or Komoot and go draw.

156 artworks · 56 Hungarian cities · Running/Cycling/Walking · GPX 1.1

## Features

### Shape library (156 artworks, 7 categories)
- **Animals** — butterfly, fish, wolf, deer, squirrel, hedgehog, bee, ant,
  spider, seahorse, jellyfish, starfish, horse, cat, dog, bird, rabbit, owl,
  swan, crow, penguin, dolphin, shark, whale, snail, frog, dragon, unicorn,
  phoenix, peacock, crab, octopus, elephant, giraffe, lion, tiger, bear,
  snake, turtle, parrot
- **Nature** — tree, flower, sun, moon, mountain, wave, lightning, snowflake,
  volcano, waterfall, rainbow, tornado, island, desert, forest, canyon,
  glacier, aurora, leaf, mushroom, cloud, droplet
- **City** — crown, castle, bridge, parliament, basilica, chain-bridge,
  opera, cathedral, windmill, lighthouse, fountain, pagoda, temple, pyramid,
  colosseum, eiffel-tower, statue, gate
- **Symbols** — heart, star, arrow, cross, infinity, peace, yin-yang,
  shield, sword, ring, crystal, gem, star8, pentagon, octagon, queen-crown,
  diamond, clover, anchor, key, lock, gear, compass, telescope
- **Sports** — bicycle, runner, swimmer, skateboard, surfboard, kayak,
  canoe, golf-club, hockey-stick, volleyball, bowling, archery-bow,
  parachute, dumbbell, target, trophy
- **Funny** — balloon, cake, ice-cream, donut, coffee, hotdog, hamburger,
  cocktail, pretzel, sunglasses, hat, mask, robot, rocket, ufo, ghost,
  skeleton, alien, smiley, wink
- **Basic** — square, circle, triangle, hexagon, spiral, zigzag, ribbon,
  loop, wavy, chevron, crosshair, grid

### City road network analysis (56 Hungarian cities)
- Activity-specific road graphs — running, cycling, walking
- Road density, bridge count, river/water boundaries
- Per-city signature shapes that fit the geography best
- Lazily loaded and LRU-cached for performance

### SVG-driven shape matching algorithm
- Parses SVG paths into weighted shape graphs (polylines + control points)
- Normalizes preserving aspect ratio, scales to target distance
- Enumerates multiple rotations, scales, and placements
- **Corridor scoring** — fast rejection of bad placements before expensive
  route construction
- **Beam search matching** — aligns shape control points to road graph nodes
- **Route construction** — connects matched segments via shortest paths
- **Scoring** — composite score from shape fidelity, distance accuracy, road
  quality, and continuity

### Generation pipeline
1. City metadata and road graph loading
2. SVG parsing into weighted shape graph
3. Shape-to-city suitability estimation
4. Anchor-based transform generation (scale + rotation + placement)
5. Corridor-based rejection scoring
6. Beam map matching to streets
7. Shape-aware route construction
8. Candidate refinement and distance calibration
9. Multi-metric scoring (shape fidelity, coverage, routeability)
10. Optional AI-assisted retry for low-confidence results
11. OpenRouteService snap-to-real-roads (when API key configured)
12. GPX 1.1 export in two modes

### GPX export modes
- **Continuous mode** — dense trackpoints following the road network. Best
  for Garmin, Komoot, and Strava navigation.
- **Connect-the-dots mode** — only key control points. Use for pause-plot
  GPS recording where straight lines are drawn between points.

### API
- RESTful JSON API with 15+ endpoints
- OpenAPI documentation at `/docs`
- Rate-limited generation, GPX download, and search
- Shareable route links via short codes
- Background job processing with real-time stage reporting

### Frontend (Next.js 15 App Router)
- Landing page with city search → compatible shape discovery
- Generation studio with step-by-step wizard
- Artwork gallery with category and difficulty filters
- City explorer with road network stats and signature shapes
- Route detail with scores, map preview, and GPX download
- Share page for public route viewing
- Hungarian (default) and English UI with instant toggle
- Leaflet-based map with route, target shape, and keypoint overlays
- Responsive design (mobile + desktop)

## API endpoints

### Health

```
GET /api/health
```

```json
{ "status": "ok", "version": "1.0.0", "db": false }
```

### Cities

```
GET /api/cities
```

Returns all 56 cities with metadata (centroid, bounding box, road density,
bridges, river presence, signature artwork IDs).

```
GET /api/cities/{city_id}
```

Returns a single city by slug (e.g. `budapest`, `debrecen`, `szeged`).

```
GET /api/cities/{city_id}/artworks?activity=running&difficulty=easy
```

Returns artworks compatible with the city. Each result includes:
`artworkId`, `artworkName`, `category`, `complexity`, `previewSvgUrl`,
`fitScore` (0–1), `minKm`, `maxKm`, `recommendedKm`, `isSignature`.

Query params:
- `activity` — `running` (default), `cycling`, `walking`
- `difficulty` — `easy`, `medium`, `hard` (optional)

### Artworks

```
GET /api/artworks
```

Returns all 156 artworks with: `id`, `name`, `category`, `complexity`,
`tags`, `cityAffinities`, `previewSvgUrl`, `recommendedDistanceKm`,
`sampleCount`, `aspectRatio`, `normalizedLength`, `isClosed`, `isSymmetric`.

```
GET /api/artworks/{artwork_id}
```

Returns a single artwork with full metadata.

```
GET /api/artworks/{artwork_id}/cities?activity=running&distance_km=8.0
```

Returns cities compatible with the artwork. Each result: `cityId`, `cityName`,
`fitScore`, `minKm`, `maxKm`, `isSignature`.

Query params:
- `activity` — `running` (default), `cycling`, `walking`
- `distance_km` — optional filter for target distance

### Generation

```
POST /api/generation/generate
```

Body:
```json
{
  "city_id": "budapest",
  "artwork_id": "heart",
  "activity": "running",
  "distance_km": 8.0
}
```

Returns:
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

```
GET /api/generation/jobs/{job_id}
```

Returns job status and progress. Stages reported in order:
`loading_city` → `loading_road_graph` → `building_indexes` →
`parsing_shapes` → `ranking_shapes` → `selecting_artworks` →
`generating_placements` → `generating_transforms` → `corridor_scoring` →
`fitting_candidates` → `beam_matching` → `constructing_routes` →
`repairing_routes` → `refining_candidates` → `scoring` →
`storing_results` → `ai_retry` → `completed`.

Completed response includes up to 5 candidates with: `id`, `scoreShape`,
`scoreRoad`, `scoreDist`, `scoreContinuity`, `compositeScore`,
`distanceKm`, `elevationGainM`, `trackPoints`, `summary`, `rotationDeg`,
`scale`.

```
GET /api/generation/jobs/{job_id}/candidates/{candidate_id}/gpx?mode=continuous
```

Downloads GPX 1.1 file. Query params:
- `mode` — `continuous` (dense, default) or `dots` (key points only)

```
GET /api/generation/jobs/{job_id}/candidates/{candidate_id}/map
```

Returns GeoJSON FeatureCollection for the candidate route (used by the
frontend Leaflet map).

### Routes (persisted)

```
GET /api/routes/{route_id}
```

Returns a persisted route with metadata and scores.

```
GET /api/routes/{route_id}/gpx?mode=continuous
```

Downloads GPX 1.1 for a persisted route.

```
GET /api/routes/{route_id}/map
```

Returns GeoJSON for a persisted route.

### Sharing

```
POST /api/shares
```

Body:
```json
{
  "route_id": "uuid"
}
```

Creates a shareable short link. Returns a short code.

```
GET /api/shares/{short_code}
```

Resolves a short code to the full route data.

## Architecture

```
pathforge/
├── app/                    # Backend (FastAPI)
│   ├── api/routers/        # Route handlers (cities, artworks, generation, ...)
│   ├── core/               # Domain logic
│   │   ├── shape_matching.py   # SVG → street matching (core algorithm)
│   │   ├── generation.py       # Orchestration / worker
│   │   ├── graph.py            # Road graph construction (OSMnx)
│   │   ├── geometry.py         # SVG anchor extraction, transforms
│   │   ├── scoring.py          # Route quality scoring
│   │   ├── gpx.py              # GPX 1.1 serialization
│   │   ├── units.py            # Projection / coordinate helpers
│   │   └── ors_client.py       # OpenRouteService snap-to-road
│   ├── models.py           # Pydantic schemas
│   ├── main.py             # FastAPI entrypoint + static mounts
│   ├── config.py           # App settings (env-based)
│   ├── graph_provider.py   # Lazy city-graph loader with LRU cache
│   ├── services.py         # Rate limiter, background worker
│   └── stores.py           # In-memory / DB stores
├── data/
│   ├── shapes/             # 156 generated SVG files
│   ├── seed/               # Seed data JSON (cities, artworks)
│   └── cache/              # LRU-cached city road graphs
├── frontend/               # Next.js 15 App Router
│   ├── app/                # Pages (/, /studio, /gallery, /cities, ...)
│   ├── components/         # UI components (Navbar, Footer, MapView, ...)
│   └── lib/                # API client, types, i18n (HU/EN)
├── docs/                   # MkDocs documentation source
├── site/                   # Built documentation (served at /documentation/)
├── scripts/
│   ├── generate_shapes.py  # SVG file generator
│   └── seed.py             # Database seeder
├── tests/
│   ├── unit/               # Unit tests (graph, geometry, generation, ...)
│   └── api/                # Integration tests (full generation flow)
└── infrastructure/         # Docker, CI/CD
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13+, FastAPI, Uvicorn |
| Geometry | Shapely, OSMnx, NetworkX |
| Frontend | Next.js 15 (App Router), TypeScript |
| Maps | Leaflet, OpenStreetMap tiles |
| Styling | Tailwind CSS v4 |
| Database | SQLite (dev), PostgreSQL + PostGIS (prod) |
| ORS | OpenRouteService API (optional road snapping) |
| Documentation | MkDocs with Material theme |
| Testing | pytest |
| Linting | Ruff, Prettier |
| Infrastructure | Docker Compose |

## Quick start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_shapes.py
python scripts/seed.py
uvicorn app.main:app --reload              # API at :8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                                 # UI at :3000

# Documentation (separate terminal)
python -m mkdocs serve                      # Docs at :8001
```

### Docker (everything at once)

```bash
docker compose up --build
```

## API docs

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **User documentation**: http://localhost:8000/documentation/ (served from
  mkdocs build via FastAPI static mount)

## Tests

```bash
python -m pytest                     # All 74 tests
python -m pytest tests/unit          # Unit tests
python -m pytest tests/api           # API integration tests
python -m pytest -q --tb=short       # Quiet, short traceback
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `CSR_ORS_API_KEY` | No | — | OpenRouteService API key |
| `CSR_ZEN_API_KEY` | No | — | Zen API key (AI retry) |
| `CSR_DATABASE_URL` | No | `sqlite://` | PostgreSQL connection |
| `CSR_DISABLE_ORS` | No | `false` | Skip ORS snapping |
| `CSR_CORS_ORIGINS` | No | `*` | Allowed CORS origins |
| `CSR_PUBLIC_WEB_URL` | No | `http://localhost:3000` | Frontend URL |

## License

Map data © OpenStreetMap contributors (ODbL). Application code provided as-is.
