# CityShapeRunner

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)
![Python Version](https://img.shields.io/badge/Python-3.13-brightgreen?style=for-the-badge&logo=python)
![React Next.js](https://img.shields.io/badge/Frontend-Next.js-black?style=for-the-badge&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![OSMnx](https://img.shields.io/badge/OSMnx-Network_Analysis-blue?style=for-the-badge)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white)
![Cities](https://img.shields.io/badge/Cities-500-orange?style=for-the-badge)
![Artworks](https://img.shields.io/badge/Artworks-500-blueviolet?style=for-the-badge)

An intelligent application that wraps beautiful GPS art over real-world road networks.
Select from 500 vector artworks and choose one of 500 Hungarian cities. The app finds the best
matching scale, rotation, and exact streets to place the artwork on, producing a continuous
GPX route that follows real streets while tracing that shape. Load it onto your
Garmin, Strava, or Komoot and go draw.

500 artworks · 500 cities · Running/Cycling/Walking · GPX 1.1

## Features

### Shape library (300 artworks, 7 categories)
- **Animals** - butterfly, fish, wolf, deer, squirrel, hedgehog, bee, ant,
  spider, seahorse, jellyfish, starfish, horse, cat, dog, bird, rabbit, owl,
  swan, crow, penguin, dolphin, shark, whale, snail, frog, dragon, unicorn,
  phoenix, peacock, crab, octopus, elephant, giraffe, lion, tiger, bear,
  snake, turtle, parrot
- **Nature** - tree, flower, sun, moon, mountain, wave, lightning, snowflake,
  volcano, waterfall, rainbow, tornado, island, desert, forest, canyon,
  glacier, aurora, leaf, mushroom, cloud, droplet
- **City** - crown, castle, bridge, parliament, basilica, chain-bridge,
  opera, cathedral, windmill, lighthouse, fountain, pagoda, temple, pyramid,
  colosseum, eiffel-tower, statue, gate
- **Symbols** - heart, star, arrow, cross, infinity, peace, yin-yang,
  shield, sword, ring, crystal, gem, star8, pentagon, octagon, queen-crown,
  diamond, clover, anchor, key, lock, gear, compass, telescope
- **Sports** - bicycle, runner, swimmer, skateboard, surfboard, kayak,
  canoe, golf-club, hockey-stick, volleyball, bowling, archery-bow,
  parachute, dumbbell, target, trophy
- **Funny** - balloon, cake, ice-cream, donut, coffee, hotdog, hamburger,
  cocktail, pretzel, sunglasses, hat, mask, robot, rocket, ufo, ghost,
  skeleton, alien, smiley, wink
- **Basic** - square, circle, triangle, hexagon, spiral, zigzag, ribbon,
  loop, wavy, chevron, crosshair, grid

### City road network analysis (500 cities in Hungary)
- Activity-specific road graphs - running, cycling, walking
- Road density, bridge count, river/water boundaries
- Per-city featured shapes that fit the geography best
- Lazily loaded and LRU-cached for performance

## The GPS Art Generation Algorithm

Mapping arbitrary 2D vector shapes onto a constrained real-world street grid is a complex, NP-hard geometric optimization problem. Our custom routing algorithm uses a multi-stage approach, leveraging spatial indices and graph traversal techniques to achieve this in under 3 seconds per shape.

### 1. Shape Normalization & Graph Transformation
- **SVG Parsing**: The 2D vector artwork (SVG) is parsed. Bezier curves are discretized into line segments based on curvature density.
- **Rescaling & Rotation**: The parsed geometry is normalized into a local metric coordinate system. The algorithm explores a configurable search space of scales (e.g., 5km, 10km, 21km targets) and rotations (0° to 360° with a dynamic step size).

### 2. Anchor-based Placement & Corridor Scoring (Heuristic Rejection)
- Instead of attempting a full graph-match for every location in a city, we extract **structural anchors** from the shape (sharp corners, bounding box extremities, centroids).
- We translate the shape over the city map using a dense grid stride. For each placement, a fast **Corridor Scoring** evaluates how many graph nodes fall within a buffer distance (e.g., 10-20 meters) of the shape's segments.
- Placements falling into water bodies or areas with zero road density are aggressively pruned.
- Only the top `N` candidates proceed to the next phase.

### 3. Beam Search Map Matching
- For the surviving placements, we align the shape's control points directly to the nearest physical nodes in the OSMnx graph using an `R-tree` spatial index.
- Since strict snapping can cause ugly detours, a **Beam Search** algorithm is employed: it traces the ideal vector path and looks for contiguous edges. It evaluates multiple branch paths simultaneously, scoring them by deviation penalty (distance from ideal path) and edge weight (road type suitability for running/cycling).

### 4. A* Route Construction & Shortest Path Bridging
- Often, the street grid doesn't perfectly match the shape, leading to gaps in the matched segments.
- The algorithm connects disjointed matched segments using a custom **A* shortest path** traversal over the road network. The heuristic combines physical distance and turn penalties.
- To ensure continuous tracking without stopping or lifting the "pen", Eulerian path algorithms and penalty graphs handle overlapping routes and backtracking efficiently.

### 5. Multi-metric Scoring & Refinement
- After constructing a full, continuous `GPX` geometry, the final route is scored across four dimensions:
  - **Shape Fidelity (0-100)**: Fréchet distance and Hausdorff distance between the original SVG and the resulting GPX path.
  - **Road Score (0-100)**: Penalizes multi-lane highways or non-pedestrian zones.
  - **Distance Match (0-100)**: How close the final generated distance is to the user's requested target.
  - **Continuity**: Evaluates necessary overlapping or detours.
- If the Mapbox integration is enabled, an optional final pass uses the `Mapbox Directions API (walking/cycling profile)` to snap raw geometry directly to precise road alignments for superior GPS device compatibility.

## A GPS Art Generáló Algoritmus (Magyar nyelvű összefoglaló)

Egy tetszőleges 2D-s vektoros alakzat valós úthálózatra való ráillesztése egy komplex, NP-nehéz geometriai optimalizációs probléma. A saját fejlesztésű algoritmus egy többlépcsős megközelítést alkalmaz, amely térbeli indexelést és gráfelméleti kereséseket használ, hogy alakzatonként 3 másodperc alatt eredményt adjon.

### 1. Alakzat normalizálás és Horgonypontos elhelyezés
- Az SVG vektorokat beolvassa, a görbéket szakaszokra bontja.
- Sűrű rácsos hálózat mentén (grid stride) végigpróbálja az alakzatot a városon, egy gyors **Corridor Scoring** heurisztikával kiszűrve az esélytelen (vízbe vagy út nélküli területekre eső) pozíciókat.

### 2. Nyalábsugár-keresés (Beam Search) a vonalillesztéshez
- A megmaradt esélyes elhelyezéseknél egy **R-tree** (térbeli indexelés) segítségével megtalálja a legközelebbi valós utakat az OSMnx gráfban.
- Szigorú illesztés helyett egy **Beam Search** algoritmust használ, amely egyszerre több lehetséges ösvényt vizsgál, büntetve a nagy kitérőket és előnyben részesítve a gyalogos/futó utakat.

### 3. A* algoritmus és útvonal összekötés
- A valós utak ritkán adják ki tökéletesen az alakzatot, így a létrejött útszakaszok között "lyukak" lesznek.
- Ezeket a szakaszokat egy egyedi **A* (A-csillag)** legrövidebb útkereső algoritmussal köti össze.
- Euler-útvonalak elveit használja az átfedések és visszafordulások kezelésére, így biztosítva, hogy az útvonal megállás nélkül, folytonosan végigfutható legyen.

### 4. Több-metrikás pontozás (Fréchet és Hausdorff távolság)
- A kész útvonal geometriai hűségét a **Fréchet távolság** és a **Hausdorff távolság** segítségével méri a rendszer, összevetve az eredeti alakzattal.
- Emellett értékeli az utak minőségét (Road Score) és a kért cél-távolságtól való eltérést is.

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
- City explorer with road network stats and featured shapes
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

Returns all 500 cities with metadata (centroid, bounding box, road density,
bridges, river presence, featured artwork IDs).

```
GET /api/cities/{city_id}
```

Returns a single city by slug (e.g. `budapest`, `debrecen`, `szeged`).

```
GET /api/cities/{city_id}/artworks?activity=running&difficulty=easy
```

Returns artworks compatible with the city. Each result includes:
`artworkId`, `artworkName`, `category`, `complexity`, `previewSvgUrl`,
`fitScore` (0-1), `minKm`, `maxKm`, `recommendedKm`, `isFeatured`.

Query params:
- `activity` - `running` (default), `cycling`, `walking`
- `difficulty` - `easy`, `medium`, `hard` (optional)

### Artworks

```
GET /api/artworks
```

Returns all 300 artworks with: `id`, `name`, `category`, `complexity`,
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
`fitScore`, `minKm`, `maxKm`, `isFeatured`.

Query params:
- `activity` - `running` (default), `cycling`, `walking`
- `distance_km` - optional filter for target distance

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
- `mode` - `continuous` (dense, default) or `dots` (key points only)

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
│   │   └── mapbox_client.py    # Mapbox Directions snap-to-road
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
| Maps | Leaflet, Mapbox |
| Mapbox | Mapbox Directions API (road snapping and routing) |
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
| `CSR_MAPBOX_ACCESS_TOKEN` | No | - | Mapbox Access Token for routing |
| `CSR_ZEN_API_KEY` | No | - | Zen API key (AI retry) |
| `CSR_DATABASE_URL` | No | `sqlite://` | PostgreSQL connection |
| `CSR_CORS_ORIGINS` | No | `*` | Allowed CORS origins |
| `CSR_PUBLIC_WEB_URL` | No | `http://localhost:3000` | Frontend URL |

## License

Map data © OpenStreetMap contributors (ODbL). Application code provided as-is.
