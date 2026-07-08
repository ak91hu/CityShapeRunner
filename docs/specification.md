# CityShapeRunner / CityArtGPX
## Engineering Design Specification for an Automated GPS Art Web Application

**Version:** 1.0.0  
**Status:** Implementation-ready specification  
**Target implementers:** CLI-based AI coding agents, software engineers, product engineers, GIS engineers  
**Primary output:** A browser-based web application that generates GPS-art routes and downloadable GPX files from city, activity, distance, and artwork inputs.  
**Document language:** English  

---

## 1. Executive Summary

CityShapeRunner is a niche web application for generating GPS art routes for runners, cyclists, and walkers. The core product promise is:

> Enter a city, choose an activity and distance, receive artwork suggestions that fit that city, preview a road-valid route, and download a GPX file.

GPS art currently requires substantial manual work. Users typically open Google Maps, OpenStreetMap, GPX Studio, RouteDoodle, Draw My Loop, or similar tools, manually draw an image, repair disconnected road sections, measure distance, and export GPX. Existing products provide useful route editors, artwork overlays, templates, snap-to-road features, or semi-automated fitting, but the researched market gap is clear: there is no mature, general-purpose product that automatically analyzes a selected city and recommends multiple city-suitable artwork shapes with generated GPX output.

This specification defines a practical engineering path for that product. It does not assume a magical "find every possible shape in a city" engine because that problem is computationally hard. Instead, the MVP is based on **anchored semi-automation with Auto-Fit**:

1. Maintain a curated artwork library.
2. Load or cache the city road network.
3. Test each candidate artwork across scales, rotations, and placements.
4. Snap artwork control points and sampled lines to the road graph.
5. Repair gaps with shortest-path routing.
6. Score candidates by shape similarity, distance accuracy, route safety, and road quality.
7. Present the best candidates as city-specific suggestions.
8. Export valid GPX in continuous road-following mode and, optionally, connect-the-dots mode.

The application should feel automatic to the user while using deterministic, inspectable engineering methods internally.

---

## 2. Market and Research Findings

### 2.1 Existing GPS Art Tools

The analyzed research identified the following relevant products and categories:

| Product | Strength | Gap relative to this project |
|---|---|---|
| Draw My Loop | 50+ templates, snap-to-road, GPX/TCX export, Auto-Fit-like placement optimization | User chooses shape and placement; no broad city-specific automatic suggestion engine |
| RouteDoodle | Image/SVG import, tracing, wireframe generation, route output | Image-first workflow; not city-first |
| GPSArtify | AI-assisted route overlay, templates, social sharing orientation | GPX export may be gated; not primarily city-specific suggestion |
| gps2gpx.art | Image overlay, freestyle/connect-the-dots GPX modes | Mostly manual tracing |
| Motera / ArtTrails | Mobile-friendly templates, gamification, tracking | Template-first, not city-first |
| WillCycle | Bicycle-focused routing with BRouter-like logic | Narrow cycling focus and manual image/point workflow |
| cityheart.run | Closest to "enter city -> route generated" | Limited to one shape category, typically heart routes |

### 2.2 Product Opportunity

The opportunity is not merely "another GPS art editor." The strongest differentiator is:

> City-first artwork recommendation.

The user should not need to know what shape will work in Budapest, Vienna, Győr, Debrecen, Amsterdam, or Paris. The system should evaluate the city and propose artwork options likely to produce recognizable routes.

### 2.3 Important Technical Reality

A fully general engine that scans any city and discovers every possible recognizable object is not realistic for an MVP. It approaches hard graph-pattern and subgraph-isomorphism problems:

- A city road network is a large graph.
- Each artwork can be represented as a graph or polyline set.
- Matching arbitrary shapes requires translation, scaling, rotation, distortion tolerance, graph connectivity, and road legality checks.
- Searching every possible shape in every possible placement is computationally expensive.

Therefore, v1 must use a bounded search:

- curated artwork library,
- limited candidate placements,
- limited rotation set,
- scale range derived from target distance,
- route graph filtering by activity profile,
- deterministic scoring and caching.

### 2.4 GPS and Urban Constraints

Generated routes must account for real-world constraints:

- Civilian GPS accuracy is often several meters and can degrade in urban canyons.
- Tall buildings, rivers, railways, industrial zones, private areas, and highways break geometric continuity.
- European and Hungarian cities often have organic, irregular, radial, or river-constrained networks rather than North American-style grids.
- Running profiles can use smaller paths, footways, parks, and stairs; cycling profiles require larger, safer, more continuous corridors.
- Small artwork below about 4-5 km may be too "pixelated" in typical road networks.
- Very large artwork can be distorted by sparse networks, highways, rivers, and suburban gaps.

---

## 3. Product Vision

CityShapeRunner should become the easiest way to create GPS art routes without manual map drawing.

The ideal user journey:

```text
Open app
-> enter city
-> choose running / cycling / walking
-> choose target distance
-> click Generate
-> review ranked artwork candidates
-> open preview
-> download GPX
```

The product should support two audiences simultaneously:

1. Beginners who want a fun Strava/Garmin route in under one minute.
2. Experienced GPS artists who want a faster starting point and can manually refine advanced outputs later.

---

## 4. Product Goals

### 4.1 Primary Goal

Generate recognizable, navigable GPS art routes from minimal user input.

Given:

- city,
- activity profile,
- target distance,
- optional difficulty,
- optional artwork preference,

the system must produce:

- ranked artwork suggestions,
- route preview,
- estimated distance,
- optional elevation summary,
- downloadable GPX 1.1 file,
- route metadata and shareable result page.

### 4.2 Secondary Goals

- Reduce planning time from hours to under one minute for cached or simple cases.
- Support both Hungarian and international cities through OpenStreetMap data.
- Preserve artwork recognizability over geometric perfection.
- Avoid unsafe or illegal roads where map data indicates restrictions.
- Provide deterministic fallback behavior when AI recommendation services are unavailable.
- Cache popular city/shape/distance combinations.
- Keep onboarding friction low; anonymous users can generate and export basic routes.

---

## 5. Guiding Principles

### 5.1 Automation First

The default flow must not require manual drawing. Manual editing can exist later as an advanced mode, but the MVP must behave like a generator rather than a drawing tool.

### 5.2 Road Reality First

Road data is the source of truth. Artwork adapts to the city; the city is never assumed to match the artwork.

### 5.3 Recognizability Over Precision

Perfect curves are less important than a recognizable final track. Scoring should prioritize human-recognizable silhouettes.

### 5.4 Deterministic Core, Optional AI

AI may help with ranking, city-signature suggestions, descriptions, or future SVG generation. The routing and GPX generation core must work without AI.

### 5.5 Explainable Generation

The system should store enough metadata to explain why a candidate was selected:

- selected placement,
- scale,
- rotation,
- shape similarity score,
- distance error,
- disconnected repairs,
- rejected roads,
- road-quality penalties.

### 5.6 Frictionless First Use

Anonymous users should be able to:

- search a city,
- generate a small number of routes,
- preview,
- export GPX.

Accounts are for saved routes, favorites, history, private galleries, and paid features.

---

## 6. Scope

### 6.1 MVP Scope

The MVP must include:

- Landing page and generation studio.
- City search using Nominatim, Photon, or compatible geocoder.
- Running, cycling, and walking profiles.
- Target distance input from 3 km to 100 km.
- Difficulty selector.
- Curated artwork library with at least 20 shapes.
- Hungarian city seed data with at least 10 cities.
- City-aware shape suggestion and ranking.
- Road graph loading from OSM/Overpass or cached extracts.
- Shape normalization, scaling, rotation, placement, and snapping.
- Route repair through routing engine.
- Route scoring.
- Interactive map preview.
- GPX 1.1 continuous route export.
- Optional connect-the-dots GPX export.
- Basic route persistence.
- Public share URL.
- Docker Compose local environment.
- OpenAPI documentation.
- Unit and integration tests for geometry/routing/GPX.

### 6.2 v1 Scope

After MVP, add:

- User accounts.
- Saved routes and favorites.
- Manual route refinement.
- Drag/scale/rotate artwork overlay.
- Custom SVG upload.
- Route gallery.
- Better caching/precomputation.
- Elevation profile.
- TCX export.
- Admin tools for artwork library.

### 6.3 Explicitly Out of Scope for MVP

- Real-time turn-by-turn navigation.
- Native mobile apps.
- FIT export.
- Direct Garmin/Strava/Komoot sync.
- Marketplace.
- Collaborative editing.
- Fully generative AI-created SVG artwork.
- Guaranteed legal/safety validation beyond map-data-based filtering.
- Universal arbitrary shape discovery from the city graph.

---

## 7. Terminology

| Term | Definition |
|---|---|
| GPS art | A route that visually forms a recognizable drawing when displayed on a map |
| Artwork | Source shape, usually SVG/polyline, used as target drawing |
| Shape | Synonym for artwork template |
| Road graph | Nodes and edges derived from OSM roads/paths |
| Node | Road intersection, endpoint, or sampled graph point |
| Edge | Traversable segment connecting graph nodes |
| Snapping | Mapping artwork points/segments to nearby graph nodes/edges |
| Map matching | Aligning coordinates or tracks to a road graph |
| Auto-Fit | Search over placement, scale, and rotation to find best route candidate |
| Candidate | A generated possible route before final ranking |
| Repair | Connecting snapped fragments through shortest-path routing |
| Continuous GPX | GPX track following real roads/paths |
| Connect-the-dots GPX | GPX track containing key points only, intended for pause-plot style GPS art |
| Pause-plot | Technique where the user pauses recording between points to create straight virtual lines |
| Activity profile | Running, cycling, or walking routing rules |
| Shape similarity | Metric describing how close the final route is to the target artwork |
| Fit score | Weighted score for ranking generated candidates |

---

## 8. Personas

### 8.1 Casual Runner

Runs 2-4 times per week, uses Strava or Garmin Connect, wants a fun route to share. Has no GIS knowledge. Needs a simple flow and trustworthy GPX export.

### 8.2 Cyclist

Rides 20-120 km routes. Needs safer roads, cycleways, low traffic, and fewer stairs/footpaths. Accepts larger artwork because cycling routes span larger areas.

### 8.3 Tourist

Visits a city and wants a memorable route linked to that city. Examples: Budapest -> bridge, parliament silhouette, Danube wave; Paris -> Eiffel Tower; Amsterdam -> bicycle.

### 8.4 Experienced GPS Artist

Already uses manual tools. Wants automation to accelerate ideation, compare candidates, and export a starting GPX that can be edited externally.

### 8.5 Event Organizer

Creates community challenges, charity events, or corporate sports activities. Needs shareable routes, predictable distances, and branded/city-specific artwork.

---

## 9. User Stories

### 9.1 Generation

- As a runner, I want to enter my city and target distance so that I receive suitable GPS art route ideas quickly.
- As a cyclist, I want cycling-specific road constraints so that the generated route avoids stairs and unsuitable paths.
- As a beginner, I want the system to pick suitable artwork automatically so that I do not need map-editing skills.
- As a tourist, I want city-signature shapes so that the route feels connected to the location.
- As a GPS artist, I want multiple scored candidates so that I can choose the best visual result.

### 9.2 Preview and Export

- As a user, I want to see the generated route on an interactive map before downloading.
- As a user, I want the exported GPX to work with Garmin, Strava, Komoot, Coros, Wahoo, and Suunto workflows.
- As a user, I want to know distance, estimated elevation, route quality, and shape score before export.
- As a user in a river-heavy city, I want an optional connect-the-dots export mode for pause-plot artwork.

### 9.3 Account and Sharing

- As an anonymous user, I want to generate and export a few routes without registering.
- As a registered user, I want to save routes and favorites.
- As an event organizer, I want public share links.

---

## 10. Success Metrics

### 10.1 Functional Metrics

- 95% of generation jobs complete successfully for supported cities and shape library items.
- 90% of completed routes stay within +/-10% of requested distance.
- 100% of exported GPX files are XML-valid GPX 1.1.
- 95% of completed routes are connected in continuous mode unless explicitly generated as connect-the-dots.
- At least 20 seed shapes and 10 seed Hungarian cities exist in MVP.

### 10.2 UX Metrics

- Median time from landing page to route preview: under 60 seconds.
- Cached suggestion response: under 1 second.
- New generation job median runtime: under 30 seconds for city-scale MVP jobs.
- At least 80% of users who download a route choose one of the top 6 suggestions.

### 10.3 System Metrics

- City search p95 latency: under 300 ms when cached.
- API p95 latency for non-generation endpoints: under 500 ms.
- Worker job timeout default: 120 seconds.
- Production target uptime: 99.5% for MVP, 99.9% for v1.

---

## 11. High-Level UX Flow

```text
Landing page
  -> City search
  -> Activity selection
  -> Distance and difficulty
  -> Generate suggestions
  -> Suggestion grid
  -> Route preview
  -> Export GPX / Share / Save
```

### 11.1 First-Run Happy Path

1. User opens landing page.
2. User types "Budapest".
3. Autocomplete shows Budapest, Hungary.
4. User selects Running.
5. User selects 10 km and Medium difficulty.
6. User clicks Generate.
7. Backend returns generation job ID.
8. UI shows progress with stages:
   - Loading road network
   - Evaluating shapes
   - Fitting candidates
   - Scoring routes
   - Preparing previews
9. Suggestion grid shows 6-12 generated options.
10. User opens "Heart" or "Danube Wave".
11. Map preview shows target artwork overlay, snapped route, start/finish, distance, fit score.
12. User downloads `budapest-heart-10k.gpx`.

### 11.2 Failed Generation Path

If generation fails:

1. Show a clear reason.
2. Suggest smaller/larger distance or different activity.
3. Offer fallback shapes known to work.
4. Do not expose stack traces.

Example message:

> We could not generate a recognizable 5 km bicycle route for this shape in the selected area. Try 10-15 km, Running mode, or a simpler shape.

---

## 12. Functional Requirements

### 12.1 City Search

The system must provide city autocomplete.

Inputs:

- query string, minimum 2 characters,
- optional country filter,
- optional language.

Returned fields:

- city display name,
- normalized city name,
- country,
- country code,
- OSM ID,
- OSM type,
- bounding box,
- centroid,
- optional administrative polygon.

Primary provider:

- Nominatim-compatible API.

Fallback provider:

- Photon-compatible API.

Caching:

- Cache city search results by normalized query for at least 24 hours.
- Cache selected city details permanently unless refreshed manually.

### 12.2 Activity Profiles

Supported profiles:

- running,
- cycling,
- walking.

Each profile defines graph filtering and edge penalties.

#### Running

Allowed/preferred:

- footway,
- path,
- pedestrian,
- residential,
- living_street,
- park paths,
- stairs with penalty,
- service roads with low traffic.

Avoid/penalize:

- trunk/primary roads without sidewalk info,
- private access,
- poor surface,
- high traffic.

Hard reject:

- motorway,
- access=no,
- construction,
- explicitly forbidden pedestrian access.

#### Cycling

Allowed/preferred:

- cycleway,
- bicycle=yes/designated,
- residential,
- tertiary with cycle infrastructure,
- service roads where allowed.

Avoid/penalize:

- stairs,
- footway without bicycle permission,
- high-speed roads,
- one-way against direction unless bicycle contraflow is tagged,
- gravel if road-bike difficulty is selected.

Hard reject:

- motorway,
- access=no,
- bicycle=no,
- construction.

#### Walking

Allowed/preferred:

- footway,
- pedestrian,
- path,
- stairs,
- parks,
- low traffic streets.

Walking can tolerate shorter distances and denser urban detail.

### 12.3 Distance

MVP input range:

- minimum: 3 km,
- maximum: 100 km,
- default: 10 km.

Tolerance:

- target: +/-5%,
- acceptable fallback: +/-10% with warning.

Distance affects:

- artwork scale,
- candidate search radius,
- shape eligibility,
- ranking.

### 12.4 Difficulty

Supported values:

- easy,
- medium,
- hard.

Difficulty affects:

- elevation penalty,
- maximum turn density,
- road complexity,
- allowed surface roughness,
- route directness.

### 12.5 Artwork Suggestions

The system must show 6-12 suggestions when possible.

Suggestion fields:

- artwork ID,
- artwork name,
- category,
- preview image/SVG,
- estimated distance,
- fit score,
- shape similarity score,
- road quality score,
- distance error,
- generation status,
- warning flags.

### 12.6 Route Preview

Preview must show:

- map tiles,
- city boundary if available,
- target artwork outline,
- generated route,
- start marker,
- finish marker,
- distance,
- elevation if available,
- score breakdown,
- export buttons.

Map engine:

- MapLibre GL JS preferred for vector tiles,
- Leaflet acceptable for MVP simplicity.

### 12.7 Export

MVP export formats:

- GPX 1.1 continuous route.
- GPX connect-the-dots route if enabled.

Future:

- TCX,
- FIT,
- PNG preview,
- SVG route overlay.

---

## 13. Non-Functional Requirements

### 13.1 Performance

- Avoid synchronous long-running generation in HTTP request threads.
- Use queue and worker for route generation.
- Cache road graphs and generated candidate metadata.
- Limit candidate search space by city size, target distance, and profile.

### 13.2 Reliability

- Generation jobs must be idempotent by request hash.
- Failed jobs must preserve error details internally.
- Users must see stable status transitions.
- GPX downloads must be served from durable storage or regenerated deterministically.

### 13.3 Security

- Validate all inputs.
- Rate-limit anonymous generation.
- Avoid server-side request forgery through geocoder/routing URL inputs.
- Use signed URLs for private downloads.
- Do not store precise user home/work locations unless explicitly saved.

### 13.4 Privacy

- Anonymous generated routes can be stored by opaque ID.
- Do not require login for MVP generation/export.
- Saved routes default to private.
- Public share links must use unguessable IDs.
- Avoid collecting unnecessary personal data.

### 13.5 Accessibility

- Keyboard-navigable forms.
- Visible focus states.
- Map controls with labels.
- Color palettes with sufficient contrast.
- Route quality not communicated by color alone.

---

## 14. Recommended Technology Stack

### 14.1 Frontend

- Next.js 15
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Zustand for local studio state
- React Hook Form
- Zod
- MapLibre GL JS or React-Leaflet

### 14.2 Backend

Preferred practical stack:

- Python FastAPI for GIS-heavy services.
- Pydantic for request/response validation.
- SQLAlchemy or SQLModel.
- Alembic migrations.
- Celery/RQ/Arq worker or BullMQ if using Node workers.

Alternative full-TypeScript stack:

- NestJS
- Prisma
- BullMQ
- TypeScript geometry packages

This specification recommends **FastAPI for the route-generation API and workers** because geometry, graph, and GIS ecosystems are stronger in Python. The frontend remains Next.js.

### 14.3 Geospatial and Routing

- PostgreSQL + PostGIS.
- OpenStreetMap via Overpass for MVP or preprocessed extracts for production.
- NetworkX for prototype graph algorithms.
- OSMnx for extracting and constructing graphs when allowed.
- OSRM, Valhalla, GraphHopper, or BRouter for production-grade routing.
- Shapely / GeoPandas / pyproj for geometry operations.
- svgpathtools or compatible parser for SVG paths.
- gpxpy or custom XML builder for GPX.

### 14.4 Infrastructure

- Docker Compose for local dev.
- Redis for queue/cache.
- S3-compatible object storage for GPX and previews.
- NGINX or cloud reverse proxy in production.

---

## 15. Monorepo Structure

```text
cityshaperunner/
  apps/
    web/
      src/
      public/
      tests/
    api/
      app/
      tests/
    worker/
      app/
      tests/
  packages/
    shared/
      schemas/
      types/
    artwork/
      shapes/
      metadata/
    docs/
  data/
    seed/
      cities.json
      artworks.json
    shapes/
      heart.svg
      star.svg
      bicycle.svg
      bridge.svg
      crown.svg
  infrastructure/
    docker/
    nginx/
  scripts/
  SPECIFICATION.md
```

---

## 16. Domain Model

### 16.1 Core Entities

- User
- City
- Artwork
- ArtworkCategory
- GenerationRequest
- GenerationJob
- RouteCandidate
- GeneratedRoute
- RouteExport
- Favorite
- ShareLink

### 16.2 Entity Responsibilities

#### City

Stores geocoded city metadata and optional polygon/bounding box.

#### Artwork

Stores source SVG, normalized geometry metadata, category, complexity, and recommended distances.

#### GenerationJob

Tracks asynchronous generation lifecycle.

#### RouteCandidate

Stores a possible generated route and score breakdown.

#### GeneratedRoute

Stores selected or completed route geometry, export paths, and metadata.

---

## 17. Database Design

Use PostgreSQL with PostGIS.

### 17.1 Tables

#### users

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE,
  display_name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### cities

```sql
CREATE TABLE cities (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  country TEXT NOT NULL,
  country_code TEXT NOT NULL,
  osm_id BIGINT,
  osm_type TEXT,
  centroid GEOGRAPHY(Point, 4326) NOT NULL,
  bbox GEOMETRY(Polygon, 4326),
  boundary GEOMETRY(MultiPolygon, 4326),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cities_normalized_name ON cities (normalized_name);
CREATE INDEX idx_cities_centroid ON cities USING GIST (centroid);
CREATE INDEX idx_cities_boundary ON cities USING GIST (boundary);
```

#### artworks

```sql
CREATE TABLE artworks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  complexity TEXT NOT NULL,
  svg_path TEXT NOT NULL,
  aspect_ratio DOUBLE PRECISION NOT NULL,
  recommended_min_km DOUBLE PRECISION NOT NULL,
  recommended_max_km DOUBLE PRECISION NOT NULL,
  default_sample_count INTEGER NOT NULL DEFAULT 200,
  is_city_signature BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_artworks_category ON artworks (category);
CREATE INDEX idx_artworks_recommended_distance
  ON artworks (recommended_min_km, recommended_max_km);
```

#### generation_jobs

```sql
CREATE TABLE generation_jobs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  city_id UUID NOT NULL REFERENCES cities(id),
  status TEXT NOT NULL,
  activity TEXT NOT NULL,
  target_distance_km DOUBLE PRECISION NOT NULL,
  difficulty TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT,
  progress_stage TEXT,
  progress_percent INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_generation_jobs_request_hash
  ON generation_jobs (request_hash);
CREATE INDEX idx_generation_jobs_status ON generation_jobs (status);
```

#### route_candidates

```sql
CREATE TABLE route_candidates (
  id UUID PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES generation_jobs(id) ON DELETE CASCADE,
  artwork_id TEXT NOT NULL REFERENCES artworks(id),
  rank INTEGER,
  status TEXT NOT NULL,
  route_geometry GEOMETRY(LineString, 4326),
  target_geometry GEOMETRY(LineString, 4326),
  distance_km DOUBLE PRECISION,
  elevation_gain_m DOUBLE PRECISION,
  fit_score DOUBLE PRECISION,
  shape_similarity_score DOUBLE PRECISION,
  distance_accuracy_score DOUBLE PRECISION,
  road_quality_score DOUBLE PRECISION,
  elevation_score DOUBLE PRECISION,
  dead_end_penalty DOUBLE PRECISION,
  placement JSONB NOT NULL DEFAULT '{}',
  warnings JSONB NOT NULL DEFAULT '[]',
  debug JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_route_candidates_job_rank ON route_candidates (job_id, rank);
CREATE INDEX idx_route_candidates_route_geometry
  ON route_candidates USING GIST (route_geometry);
```

#### generated_routes

```sql
CREATE TABLE generated_routes (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  candidate_id UUID REFERENCES route_candidates(id),
  city_id UUID NOT NULL REFERENCES cities(id),
  artwork_id TEXT NOT NULL REFERENCES artworks(id),
  activity TEXT NOT NULL,
  distance_km DOUBLE PRECISION NOT NULL,
  elevation_gain_m DOUBLE PRECISION,
  route_geometry GEOMETRY(LineString, 4326) NOT NULL,
  gpx_storage_key TEXT,
  preview_storage_key TEXT,
  visibility TEXT NOT NULL DEFAULT 'private',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### route_exports

```sql
CREATE TABLE route_exports (
  id UUID PRIMARY KEY,
  route_id UUID NOT NULL REFERENCES generated_routes(id) ON DELETE CASCADE,
  export_type TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 18. Artwork Library

### 18.1 MVP Categories

- Basic: heart, star, circle, smiley.
- Animals: dog, cat, fish, bird, rabbit, dinosaur.
- Sports: bicycle, runner, trophy.
- Nature: tree, leaf, mountain, flower, sun.
- City/landmark: bridge, crown, parliament silhouette, river wave, castle.
- Funny: duck, pizza, beer, rocket.

### 18.2 Artwork Metadata

Each artwork must have:

```json
{
  "id": "heart",
  "name": "Heart",
  "category": "basic",
  "complexity": "easy",
  "recommended_min_km": 5,
  "recommended_max_km": 15,
  "aspect_ratio": 1.0,
  "closed_path": true,
  "default_sample_count": 160,
  "tags": ["love", "beginner", "running"],
  "city_affinity_tags": ["romantic", "park", "river"]
}
```

### 18.3 SVG Rules

MVP artwork SVGs must:

- use simple paths or polylines,
- avoid filled-only complex shapes without clear outlines,
- be normalized to a known viewBox,
- be convertible into ordered polylines,
- include metadata describing whether the path is open or closed.

---

## 19. Geometry Engine

The geometry engine transforms artwork into candidate geographic target lines.

### 19.1 Responsibilities

- Parse SVG.
- Convert paths to polylines.
- Sample Bezier curves.
- Simplify or densify polylines.
- Normalize artwork coordinates to `[0, 1]`.
- Preserve aspect ratio.
- Scale to approximate target distance.
- Rotate.
- Translate.
- Convert projected metric coordinates to WGS84.
- Compute similarity metrics.

### 19.2 SVG to Polyline

Algorithm:

1. Load SVG.
2. Extract path, polyline, line, circle, ellipse, rect primitives.
3. Convert all primitives into one or more ordered polylines.
4. Sample curves at sufficient resolution.
5. Normalize coordinates.
6. Preserve path ordering.
7. Store canonical normalized polyline.

### 19.3 Coordinate Systems

Do not perform distance calculations directly in latitude/longitude.

Workflow:

1. Convert city centroid to suitable local projected CRS.
2. Transform city boundary and road graph to local metric coordinates.
3. Run geometry operations in meters.
4. Transform final route back to WGS84 for GeoJSON/GPX.

### 19.4 Scale Estimation

For a normalized artwork with total polyline length `L_norm`, target distance `D_m`, and expected route detour factor `F`, estimate scale:

```text
scale_m = D_m / (L_norm * F)
```

Typical detour factor:

- running dense urban: 1.10-1.35,
- cycling: 1.20-1.60,
- sparse networks: 1.50-2.20.

Generate scale candidates around this estimate:

```text
scale_candidates = [
  0.75 * scale_m,
  0.90 * scale_m,
  1.00 * scale_m,
  1.10 * scale_m,
  1.25 * scale_m
]
```

---

## 20. Road Graph Engine

### 20.1 Graph Construction

Input:

- OSM ways/nodes from Overpass or extracts.

Output:

- weighted directed or undirected graph depending on profile.

Each edge must include:

- geometry,
- length_m,
- highway type,
- surface,
- smoothness,
- access tags,
- bicycle tags,
- foot tags,
- oneway tags,
- bridge/tunnel tags,
- stairs flag,
- estimated safety penalty,
- final profile-specific weight.

### 20.2 OSM Tag Filtering

Hard excluded by default:

- `highway=motorway`,
- `highway=motorway_link`,
- `access=no`,
- `construction=*`,
- `abandoned=*`,
- impassable barriers,
- routes outside city or search polygon unless allowed by margin.

### 20.3 Edge Weight Formula

Base:

```text
edge_weight = length_m * profile_multiplier + penalties
```

Penalties:

```text
penalties =
  access_penalty
+ surface_penalty
+ traffic_penalty
+ stairs_penalty
+ one_way_penalty
+ private_penalty
+ elevation_penalty
```

The routing engine should be configurable by profile and difficulty.

### 20.4 Spatial Indexing

Use spatial indexes for:

- nearest edge lookup,
- nearest node lookup,
- candidate placement validation,
- clipping to city boundary.

In Python:

- Shapely STRtree or GeoPandas spatial index.

In PostGIS:

- GiST indexes.

---

## 21. Inverse Routing and Auto-Fit Engine

### 21.1 Purpose

Traditional routing finds the fastest path from A to B. GPS art generation finds a path that resembles a target drawing. This is inverse routing.

### 21.2 Candidate Search

Inputs:

- city geometry,
- road graph,
- artwork polyline,
- target distance,
- activity profile,
- difficulty.

Search dimensions:

- artwork,
- placement,
- scale,
- rotation,
- route repair strategy.

### 21.3 Placement Generation

MVP placement strategy:

1. Compute usable city area from boundary or bbox.
2. Create grid points over usable area.
3. Remove grid points too close to excluded zones.
4. Prefer areas with high road density.
5. Limit to top N placement anchors.

Default:

- 20 placement anchors per city for synchronous suggestion prefilter,
- up to 100 anchors in background worker for high-quality generation.

### 21.4 Rotation Candidates

Default rotations:

```text
0, 15, 30, 45, 60, 75, 90, 120, 150, 180, 210, 240, 270, 300, 330 degrees
```

For symmetric shapes, reduce rotations.

### 21.5 Candidate Algorithm

```pseudo
for artwork in eligible_artworks:
  normalized = load_normalized_polyline(artwork)
  for scale in scale_candidates(target_distance, artwork):
    for rotation in rotation_candidates(artwork):
      for anchor in placement_candidates(city, road_density):
        target = transform(normalized, scale, rotation, anchor)
        if not target_fits_city_bounds(target):
          continue
        snapped = snap_target_to_graph(target, road_graph, profile)
        repaired = repair_snapped_segments(snapped, road_graph, profile)
        if repaired.invalid:
          continue
        score = score_candidate(target, repaired, target_distance, profile)
        persist_candidate(score, geometry, debug)
return top_candidates
```

### 21.6 Search Budget

MVP must enforce budgets:

- maximum candidate evaluations per job,
- maximum route calls,
- maximum worker time,
- maximum road graph size,
- maximum sampled points per artwork.

Default worker limits:

- 120 seconds per job,
- 1,000 candidate transformations,
- 100 expensive route repairs,
- 12 returned candidates.

---

## 22. Snapping Engine

### 22.1 Point Snapping

For each sampled artwork point:

1. Find nearest traversable edge.
2. Project point onto edge geometry.
3. Record snapped coordinate and edge ID.
4. Reject if distance exceeds tolerance.

Default tolerance:

- running: 80 m,
- walking: 60 m,
- cycling: 150 m,
- adjustable by city density.

### 22.2 Segment Snapping

Point snapping alone can produce disconnected or zigzag routes. Segment snapping must:

1. Sample artwork polyline at control intervals.
2. Snap key control points.
3. Route between consecutive snapped points using profile-weighted shortest path.
4. Preserve order.

### 22.3 Repair

When two snapped points are not directly connected:

- run A* or Dijkstra over the profile graph,
- use geometry-aware weight that favors staying close to target segment,
- reject if detour ratio is too high.

Detour ratio:

```text
detour_ratio = routed_segment_length / straight_target_segment_length
```

Default maximum:

- running: 4.0,
- walking: 4.0,
- cycling: 3.0,
- easy difficulty: stricter.

---

## 23. Scoring Engine

### 23.1 Score Components

Final fit score:

```text
fit_score =
  0.45 * shape_similarity_score
+ 0.20 * distance_accuracy_score
+ 0.20 * road_quality_score
+ 0.10 * continuity_score
+ 0.05 * elevation_score
- penalties
```

### 23.2 Shape Similarity

Use a combination of:

- normalized Hausdorff distance,
- Fréchet distance approximation,
- turning-angle similarity,
- bounding box aspect ratio similarity,
- route-to-target average distance,
- recognizable key point preservation.

### 23.3 Distance Accuracy

```text
distance_error = abs(actual_distance - target_distance) / target_distance
distance_accuracy_score = max(0, 1 - distance_error / tolerance)
```

### 23.4 Road Quality

Road quality should reward:

- cycleways for cycling,
- parks and footpaths for running/walking,
- low-traffic streets,
- good surface,
- legal access,
- fewer unsafe road classes.

It should penalize:

- private access,
- unknown access,
- stairs for cycling,
- highway-like roads,
- excessive repeated roads,
- too many U-turns.

### 23.5 Warning Flags

Candidates can be shown with warnings:

- `distance_outside_preferred_tolerance`,
- `contains_private_access_penalty`,
- `contains_stairs`,
- `high_detour_ratio`,
- `low_shape_similarity`,
- `route_crosses_city_boundary`,
- `connect_the_dots_recommended`.

---

## 24. GPX Generation

### 24.1 GPX Requirements

Generate GPX 1.1 XML:

- valid XML declaration,
- `<gpx version="1.1" creator="CityShapeRunner">`,
- metadata,
- one `<trk>`,
- one or more `<trkseg>`,
- ordered `<trkpt lat="" lon="">`,
- optional `<ele>`,
- optional `<time>` omitted by default unless simulating activity time.

### 24.2 File Naming

```text
{city-slug}-{artwork-slug}-{distance-rounded}k-{activity}.gpx
```

Example:

```text
budapest-heart-10k-running.gpx
```

### 24.3 Continuous GPX

Continuous mode exports full route geometry.

Use when:

- route follows real accessible network,
- user wants Garmin/Komoot navigation,
- no intentional pause-plot lines.

### 24.4 Connect-the-Dots GPX

Connect-the-dots mode exports only key route points/control points.

Use when:

- city obstacles make continuous drawing impossible,
- user wants pause-plot effect,
- artwork contains straight lines crossing rivers/blocks.

The UI must clearly explain that this mode may not represent a physically continuous route and requires manual pause/resume behavior during activity recording.

### 24.5 Validation

Every exported GPX must pass:

- XML parse validation,
- coordinate range validation,
- minimum trackpoint count,
- no NaN values,
- total distance recomputation sanity check.

---

## 25. AI Recommendation Engine

### 25.1 MVP Approach

AI is optional and should not be required for routing.

MVP city-aware recommendations can be deterministic:

- road density,
- city size,
- presence of rivers,
- bridge count,
- parks,
- known landmarks from seed metadata,
- artwork tags,
- target distance.

### 25.2 City Signature Shapes

Seed examples:

| City | Signature suggestions |
|---|---|
| Budapest | Parliament silhouette, Danube wave, bridge, crown, heart |
| Veszprém | Castle, viaduct, crown |
| Debrecen | Great Church silhouette, flower, heart |
| Pécs | cathedral, mountain, sun |
| Győr | river wave, heart, bridge |
| Szeged | sun, river, cathedral |

### 25.3 Future AI Features

- Natural language prompt: "Generate a 15 km dragon in Vienna."
- SVG generation from prompt.
- City POI analysis.
- Landmark silhouette generation.
- Automatic route explanation.
- Ranking model trained on user downloads and likes.

---

## 26. API Specification

All API responses must use JSON unless returning file downloads.

### 26.1 City Search

```http
GET /api/cities/search?q=Budapest&country=HU
```

Response:

```json
[
  {
    "id": "city_budapest_hu",
    "name": "Budapest",
    "country": "Hungary",
    "countryCode": "HU",
    "osmId": 2401090,
    "bbox": [18.925, 47.349, 19.334, 47.613],
    "centroid": { "lat": 47.4979, "lon": 19.0402 }
  }
]
```

### 26.2 Artwork Catalog

```http
GET /api/artworks?activity=running&distanceKm=10
```

Response:

```json
{
  "items": [
    {
      "id": "heart",
      "name": "Heart",
      "category": "basic",
      "complexity": "easy",
      "recommendedMinKm": 5,
      "recommendedMaxKm": 15,
      "previewSvgUrl": "/assets/shapes/heart.svg"
    }
  ]
}
```

### 26.3 Suggest Shapes / Create Generation Job

```http
POST /api/generation/jobs
Content-Type: application/json
```

Request:

```json
{
  "cityId": "city_budapest_hu",
  "activity": "running",
  "targetDistanceKm": 10,
  "difficulty": "medium",
  "artworkIds": null,
  "maxSuggestions": 12
}
```

Response:

```json
{
  "jobId": "0d0c5371-2f2a-4b51-8e3f-4c7e45e63a6b",
  "status": "queued"
}
```

### 26.4 Job Status

```http
GET /api/generation/jobs/{jobId}
```

Response:

```json
{
  "jobId": "0d0c5371-2f2a-4b51-8e3f-4c7e45e63a6b",
  "status": "processing",
  "progressStage": "fitting_candidates",
  "progressPercent": 62
}
```

Completed response:

```json
{
  "jobId": "0d0c5371-2f2a-4b51-8e3f-4c7e45e63a6b",
  "status": "completed",
  "suggestions": [
    {
      "candidateId": "cand_heart_001",
      "artworkId": "heart",
      "artworkName": "Heart",
      "rank": 1,
      "distanceKm": 10.18,
      "fitScore": 0.91,
      "shapeSimilarityScore": 0.88,
      "roadQualityScore": 0.94,
      "warnings": [],
      "previewGeoJsonUrl": "/api/candidates/cand_heart_001/geojson"
    }
  ]
}
```

### 26.5 Candidate GeoJSON

```http
GET /api/candidates/{candidateId}/geojson
```

Response:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "kind": "route" },
      "geometry": { "type": "LineString", "coordinates": [] }
    },
    {
      "type": "Feature",
      "properties": { "kind": "target_artwork" },
      "geometry": { "type": "LineString", "coordinates": [] }
    }
  ]
}
```

### 26.6 Create Route from Candidate

```http
POST /api/routes
Content-Type: application/json
```

Request:

```json
{
  "candidateId": "cand_heart_001"
}
```

Response:

```json
{
  "routeId": "route_123",
  "distanceKm": 10.18,
  "gpxUrl": "/api/routes/route_123/export/gpx",
  "shareUrl": "/r/abcDEF123"
}
```

### 26.7 GPX Export

```http
GET /api/routes/{routeId}/export/gpx?mode=continuous
```

Returns:

- `Content-Type: application/gpx+xml`
- `Content-Disposition: attachment; filename="budapest-heart-10k-running.gpx"`

### 26.8 Error Response

```json
{
  "error": {
    "code": "GENERATION_NO_VALID_CANDIDATE",
    "message": "No valid route candidate could be generated for the selected city, activity, and distance.",
    "details": {
      "suggestedActions": [
        "Increase target distance",
        "Try Running mode",
        "Choose an easier shape"
      ]
    }
  }
}
```

---

## 27. Queue and Worker System

### 27.1 Job Lifecycle

Statuses:

- queued,
- processing,
- completed,
- failed,
- cancelled.

Stages:

- loading_city,
- loading_road_graph,
- selecting_artworks,
- generating_placements,
- fitting_candidates,
- repairing_routes,
- scoring,
- storing_results,
- completed.

### 27.2 Worker Responsibilities

The worker must:

1. Load job.
2. Resolve city and graph.
3. Select eligible artworks.
4. Generate candidates.
5. Score and persist top candidates.
6. Generate preview GeoJSON.
7. Mark job completed or failed.

### 27.3 Idempotency

Compute request hash from:

- city ID,
- activity,
- target distance,
- difficulty,
- artwork ID list,
- algorithm version.

If a completed job with the same hash exists, return it instead of recomputing unless `force=true`.

---

## 28. Caching Strategy

Cache layers:

1. Geocoder query cache.
2. City boundary cache.
3. OSM road graph cache.
4. Artwork normalized polyline cache.
5. Candidate generation result cache.
6. GPX export cache.

Precompute popular combinations:

- Budapest + Heart + Running + 10 km.
- Budapest + Danube Wave + Running + 10 km.
- Budapest + Bridge + Cycling + 25 km.
- Veszprém + Castle + Running + 8 km.
- Debrecen + Flower + Running + 10 km.

---

## 29. Frontend Specification

### 29.1 Pages

#### `/`

Landing page with:

- hero value proposition,
- city search,
- examples,
- "Generate route" CTA.

#### `/studio`

Main generation studio:

- map,
- sidebar controls,
- suggestion panel,
- preview/export panel.

#### `/routes/[routeId]`

Saved route view:

- map preview,
- metadata,
- export buttons,
- share controls.

#### `/r/[shareId]`

Public shared route page.

### 29.2 Studio Layout

Desktop:

- 70-80% map.
- Right or left sidebar for controls.
- Bottom drawer for suggestions.

Mobile:

- Fullscreen map.
- Bottom sheet for controls.
- Sticky export CTA.

### 29.3 Components

- `CitySearchInput`
- `ActivitySelector`
- `DistanceSlider`
- `DifficultySelector`
- `GenerateButton`
- `GenerationProgress`
- `SuggestionGrid`
- `SuggestionCard`
- `RouteMap`
- `LayerToggle`
- `ScoreBreakdown`
- `ExportPanel`
- `WarningBanner`
- `ShareDialog`

### 29.4 State Model

Studio state:

```ts
type Activity = "running" | "cycling" | "walking";
type Difficulty = "easy" | "medium" | "hard";

interface StudioState {
  city: CitySuggestion | null;
  activity: Activity;
  targetDistanceKm: number;
  difficulty: Difficulty;
  selectedCandidateId: string | null;
  jobId: string | null;
  mapViewport: {
    lat: number;
    lon: number;
    zoom: number;
  };
}
```

### 29.5 UX Copy Principles

- Explain constraints plainly.
- Avoid overpromising safety.
- Show actionable fixes for failure.
- Distinguish continuous GPX from connect-the-dots GPX.

---

## 30. Authentication and Authorization

### 30.1 MVP

Authentication is optional.

Anonymous users:

- can search cities,
- can generate limited routes,
- can download limited GPX files,
- cannot save private history across devices.

### 30.2 v1

Login methods:

- email magic link,
- Google,
- GitHub.

Roles:

- anonymous,
- user,
- pro_user,
- admin.

Authorization:

- Private routes visible only to owner.
- Public share routes visible by share ID.
- Admin can manage artwork catalog.

---

## 31. Security and Abuse Controls

### 31.1 Rate Limits

Anonymous:

- city search: 60/min/IP,
- generation jobs: 5/day/IP,
- GPX downloads: 10/day/IP.

Authenticated free:

- generation jobs: 20/day/user.

Pro:

- higher limits configurable.

### 31.2 Input Validation

Validate:

- city ID exists,
- activity enum,
- distance range,
- difficulty enum,
- artwork IDs exist,
- max suggestions bounded.

### 31.3 External API Protection

- Never pass arbitrary user-provided URLs to server fetchers.
- Use allowlisted providers.
- Timeout all external calls.
- Cache and debounce geocoder calls.

---

## 32. Error Handling

### 32.1 Error Codes

| Code | Meaning |
|---|---|
| CITY_NOT_FOUND | City search returned no valid city |
| CITY_BOUNDARY_UNAVAILABLE | Boundary/polygon could not be loaded |
| ROAD_GRAPH_UNAVAILABLE | OSM/graph data unavailable |
| ROAD_GRAPH_TOO_LARGE | Graph exceeded MVP processing limits |
| ARTWORK_NOT_FOUND | Requested artwork does not exist |
| GENERATION_TIMEOUT | Worker exceeded time limit |
| GENERATION_NO_VALID_CANDIDATE | No route passed validation |
| GPX_EXPORT_FAILED | GPX could not be generated |
| RATE_LIMITED | User exceeded generation limit |

### 32.2 User-Facing Error Examples

No valid route:

> No recognizable route could be generated for this shape and distance. Try a longer distance, a simpler shape, or Running mode.

Graph unavailable:

> We could not load road data for this city right now. Please try again later.

Rate limited:

> You reached today's free generation limit. Try again tomorrow or sign in for more.

---

## 33. Observability

### 33.1 Logging

Log structured events:

- job created,
- graph loaded,
- candidate evaluated,
- candidate rejected,
- candidate accepted,
- job completed,
- job failed,
- GPX exported.

Do not log:

- sensitive tokens,
- precise user identity in public logs,
- private route URLs unless necessary.

### 33.2 Metrics

Track:

- generation duration,
- success/failure rate,
- external API latency,
- cache hit rate,
- candidate count,
- average fit score,
- GPX export count,
- route downloads by artwork/city.

### 33.3 Debug Artifacts

For failed jobs, store internal debug metadata:

- candidate rejection reasons,
- graph size,
- OSM data age,
- scale/rotation tested,
- exception type.

---

## 34. Testing Strategy

### 34.1 Unit Tests

Geometry:

- SVG parser handles paths and polylines.
- Normalization preserves aspect ratio.
- Scale/rotation/translation are correct.
- Distance calculations use projected CRS.

Snapping:

- nearest edge lookup works.
- out-of-tolerance points are rejected.
- segment repair connects valid graph nodes.

Scoring:

- distance score decreases with error.
- road penalties affect ranking.
- high similarity beats poor similarity.

GPX:

- XML valid.
- coordinates valid.
- continuous and connect-the-dots modes differ correctly.

### 34.2 Integration Tests

- City search with mocked provider.
- Generate route for seeded mini-city graph.
- Worker job lifecycle.
- Route candidate stored in database.
- GPX download endpoint.

### 34.3 E2E Tests

Use Playwright:

1. Open app.
2. Search Budapest.
3. Select running and 10 km.
4. Generate route with mocked backend or deterministic small fixture.
5. Open preview.
6. Download GPX.
7. Assert file extension and basic XML content.

### 34.4 Golden Test Fixtures

Maintain deterministic fixtures:

- `mini_grid_city.osm`
- `mini_irregular_city.osm`
- `heart.svg`
- `star.svg`
- expected route metrics.

---

## 35. Deployment

### 35.1 Local Docker Compose

Services:

- web,
- api,
- worker,
- postgres-postgis,
- redis,
- minio,
- nginx optional.

### 35.2 Required Environment Variables

```text
DATABASE_URL=
REDIS_URL=
S3_ENDPOINT=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
NOMINATIM_BASE_URL=
PHOTON_BASE_URL=
OVERPASS_BASE_URL=
OSRM_BASE_URL=
JWT_SECRET=
PUBLIC_WEB_URL=
API_BASE_URL=
```

### 35.3 Production Notes

- Prefer preprocessed OSM extracts for reliability.
- Public Overpass/Nominatim services should not be abused.
- Use provider-compliant User-Agent and caching.
- Separate worker autoscaling from API.
- Store generated outputs in object storage.

---

## 36. Implementation Roadmap

### Phase 0: Repository and Tooling

- Initialize monorepo.
- Add Next.js app.
- Add FastAPI app.
- Add worker app.
- Add Docker Compose.
- Add Postgres/PostGIS and Redis.
- Add lint/test/format commands.

### Phase 1: Static Prototype

- Render map.
- Add city search with mocked data.
- Add activity/distance controls.
- Add shape library seed SVGs.
- Display selected artwork overlay.

### Phase 2: Backend Foundations

- Database schema and migrations.
- City search endpoint.
- Artwork catalog endpoint.
- Job creation/status endpoint.
- Basic worker loop.

### Phase 3: Geometry and GPX

- SVG parsing.
- Polyline normalization.
- Transform to city area.
- Generate mock route.
- Export valid GPX.

### Phase 4: Road Graph and Snapping

- Load OSM graph for test cities.
- Build profile-weighted graph.
- Implement nearest-edge snapping.
- Implement segment routing/repair.
- Render generated GeoJSON.

### Phase 5: Auto-Fit and Scoring

- Candidate placements.
- Scale/rotation search.
- Score candidates.
- Return top suggestions.
- Store debug metadata.

### Phase 6: UX Completion

- Progress UI.
- Suggestion grid.
- Route preview.
- Export panel.
- Warnings and errors.
- Share links.

### Phase 7: Hardening

- Rate limits.
- Caching.
- Observability.
- Tests.
- Production deployment docs.

---

## 37. AI Coding Agent Instructions

This project is intended to be implemented by CLI-based AI coding agents. Agents must follow these rules:

1. Implement deterministic MVP functionality before optional AI features.
2. Do not build a universal arbitrary shape discovery engine in MVP.
3. Keep routing and geometry code covered by tests.
4. Do not calculate geospatial distances directly in unprojected latitude/longitude.
5. Use profile-specific road filtering and penalties.
6. GPX export must be valid even when route generation is approximate.
7. Separate API request handling from generation workers.
8. Preserve debug metadata for candidate scoring.
9. Rate-limit expensive generation.
10. Keep anonymous user flow functional.
11. Make all external provider URLs configurable and allowlisted.
12. Prefer clear error messages over silent fallbacks.
13. Use seeded fixture graphs for tests instead of relying on live OSM in CI.
14. Use explicit types/schemas for all API contracts.
15. Avoid overengineering marketplace, social feed, or mobile app features before MVP.

---

## 38. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Public OSM APIs rate-limit the app | Generation unreliable | Cache aggressively, support extracts, configure providers |
| Shape matching quality poor in organic cities | Bad UX | Rank only good candidates, suggest different distance/activity |
| Generation too slow | Users abandon | Queue jobs, cache popular combos, restrict search budget |
| Unsafe roads generated | User harm | OSM access filtering, warnings, conservative profiles |
| GPX incompatible with devices | Export failure | Strict GPX 1.1 validation and device smoke tests |
| MVP becomes too broad | Delivery delay | Keep accounts/manual editor/AI SVG out of MVP |
| Connect-the-dots misunderstood | User confusion | Clear UI explanation and separate export label |

---

## 39. Monetization Options

Free:

- limited daily generation,
- standard shapes,
- GPX export,
- public share link.

Pro:

- unlimited generation,
- high-quality search mode,
- custom SVG upload,
- city-signature packs,
- saved private routes,
- TCX/FIT export,
- route editing,
- Strava/Garmin integrations,
- batch/event generation.

Business/Event:

- branded artwork,
- private event route pages,
- team challenge dashboards,
- tourism campaign routes.

---

## 40. Future Roadmap

### v1.1

- Manual drag/scale/rotate editor.
- Custom SVG upload.
- Elevation chart.
- TCX export.
- Improved city-signature metadata.

### v1.2

- Public route gallery.
- User profiles.
- Likes/favorites.
- Route remixing.

### v2

- AI SVG generation.
- Natural language route prompts.
- Graph neural network experiments for hidden shape discovery.
- Mobile app.
- Garmin/Strava/Komoot integration.
- Marketplace.

---

## 41. Definition of Done for MVP

The MVP is complete when:

- A user can search a city.
- A user can choose running/cycling/walking.
- A user can set a target distance.
- The backend can generate ranked artwork route candidates using real or fixture OSM road data.
- The frontend can preview candidates on a map.
- The user can download valid GPX.
- Continuous GPX export works.
- Connect-the-dots export is available or explicitly deferred behind a feature flag.
- At least 20 artwork templates are seeded.
- At least 10 Hungarian cities are seeded.
- Docker Compose starts the stack locally.
- OpenAPI docs are available.
- Unit tests cover geometry, scoring, and GPX export.
- An E2E test covers the happy path from city selection to GPX download.

---

## 42. Appendix A: Seed Hungarian Cities

MVP seed cities:

- Budapest
- Debrecen
- Szeged
- Miskolc
- Pécs
- Győr
- Nyíregyháza
- Kecskemét
- Székesfehérvár
- Veszprém
- Eger
- Gyöngyös

Gyöngyös is important because Hungarian GPS art examples demonstrate that the city and surrounding agricultural areas can support large GPS drawings.

---

## 43. Appendix B: Example Artwork Seed List

```json
[
  { "id": "heart", "name": "Heart", "category": "basic", "complexity": "easy", "recommended_min_km": 5, "recommended_max_km": 15 },
  { "id": "star", "name": "Star", "category": "basic", "complexity": "easy", "recommended_min_km": 5, "recommended_max_km": 20 },
  { "id": "bicycle", "name": "Bicycle", "category": "sports", "complexity": "hard", "recommended_min_km": 20, "recommended_max_km": 80 },
  { "id": "runner", "name": "Runner", "category": "sports", "complexity": "medium", "recommended_min_km": 10, "recommended_max_km": 30 },
  { "id": "bridge", "name": "Bridge", "category": "city", "complexity": "medium", "recommended_min_km": 8, "recommended_max_km": 25 },
  { "id": "danube-wave", "name": "Danube Wave", "category": "city", "complexity": "medium", "recommended_min_km": 8, "recommended_max_km": 30 },
  { "id": "crown", "name": "Crown", "category": "city", "complexity": "medium", "recommended_min_km": 8, "recommended_max_km": 25 },
  { "id": "dog", "name": "Dog", "category": "animals", "complexity": "medium", "recommended_min_km": 8, "recommended_max_km": 25 },
  { "id": "cat", "name": "Cat", "category": "animals", "complexity": "medium", "recommended_min_km": 8, "recommended_max_km": 25 },
  { "id": "dinosaur", "name": "Dinosaur", "category": "animals", "complexity": "hard", "recommended_min_km": 15, "recommended_max_km": 60 }
]
```

---

## 44. Appendix C: Minimal GPX Example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="CityShapeRunner" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>Budapest Heart 10K Running</name>
  </metadata>
  <trk>
    <name>Budapest Heart 10K Running</name>
    <trkseg>
      <trkpt lat="47.497900" lon="19.040200" />
      <trkpt lat="47.498100" lon="19.041000" />
    </trkseg>
  </trk>
</gpx>
```

---

## 45. Appendix D: Candidate Debug Metadata Example

```json
{
  "algorithmVersion": "mvp-0.1",
  "placement": {
    "anchorLat": 47.4979,
    "anchorLon": 19.0402,
    "scaleMeters": 1250,
    "rotationDegrees": 45
  },
  "search": {
    "placementsTested": 40,
    "rotationsTested": 12,
    "scalesTested": 5,
    "routeRepairsAttempted": 84
  },
  "scores": {
    "fitScore": 0.91,
    "shapeSimilarity": 0.88,
    "distanceAccuracy": 0.96,
    "roadQuality": 0.94,
    "continuity": 1.0,
    "elevation": 0.72
  },
  "warnings": []
}
```

---

## 46. Detailed System Architecture

### 46.1 C4 Context

```mermaid
flowchart LR
    User[Runner / Cyclist / Tourist] --> Web[CityShapeRunner Web App]
    Web --> Api[CityShapeRunner API]
    Api --> Db[(PostgreSQL + PostGIS)]
    Api --> Redis[(Redis)]
    Api --> Worker[Generation Worker]
    Worker --> Db
    Worker --> Redis
    Worker --> Storage[(S3-compatible Storage)]
    Api --> Storage
    Api --> Geocoder[Nominatim / Photon]
    Worker --> OSM[Overpass / OSM Extracts]
    Worker --> Router[OSRM / Valhalla / GraphHopper / BRouter]
    User --> Device[Garmin / Strava / Komoot / Coros / Wahoo]
    Web --> Device
```

### 46.2 Container Responsibilities

| Container | Responsibility | Must not do |
|---|---|---|
| Web | UI, map rendering, form state, job polling, preview, GPX download | Heavy route generation, direct Overpass abuse |
| API | Auth, validation, city/artwork catalog, job orchestration, file serving | CPU-heavy graph search in request thread |
| Worker | OSM graph processing, geometry fitting, routing, scoring, export generation | User session management |
| PostgreSQL/PostGIS | Durable domain data, city/artwork metadata, route geometry | Ephemeral progress pub/sub |
| Redis | Queue, progress cache, rate limit counters, short-lived cache | Long-term route storage |
| Object storage | GPX, preview images, generated GeoJSON artifacts | Primary relational metadata |

### 46.3 Backend Component Diagram

```mermaid
flowchart TB
    Api[FastAPI Application]
    Api --> Validation[Pydantic Schemas]
    Api --> RateLimit[Rate Limit Service]
    Api --> CityService[City Service]
    Api --> ArtworkService[Artwork Service]
    Api --> JobService[Generation Job Service]
    Api --> RouteService[Route Service]
    Api --> ExportService[Export Service]

    Worker[Generation Worker]
    Worker --> GraphService[Road Graph Service]
    Worker --> GeometryService[Geometry Engine]
    Worker --> SnappingService[Snapping Engine]
    Worker --> RoutingService[Routing Adapter]
    Worker --> ScoringService[Scoring Engine]
    Worker --> GpxService[GPX Generator]
    Worker --> StorageService[Storage Service]
```

### 46.4 Critical Architectural Constraints

1. The API must remain responsive while generation jobs run.
2. Every expensive operation must be bounded by time, memory, and candidate count.
3. All generation algorithms must be deterministic for the same inputs and algorithm version.
4. External provider integrations must be replaceable through adapter interfaces.
5. The route-generation worker must support fixture graphs for deterministic tests.
6. Geometry and graph code must avoid hidden global state.
7. Algorithm versions must be stored with candidate results so future changes do not silently alter old routes.

---

## 47. Detailed API Contract

### 47.1 Shared Response Envelope

Successful list responses:

```json
{
  "items": [],
  "meta": {
    "requestId": "req_...",
    "cached": false
  }
}
```

Errors:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "fields": {
      "targetDistanceKm": "Must be between 3 and 100."
    },
    "requestId": "req_..."
  }
}
```

### 47.2 API Endpoint Inventory

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | no | Liveness check |
| GET | `/api/ready` | no | Readiness check with DB/Redis |
| GET | `/api/cities/search` | no | Geocoder autocomplete |
| GET | `/api/cities/{cityId}` | no | City detail |
| GET | `/api/artworks` | no | Artwork catalog |
| GET | `/api/artworks/{artworkId}` | no | Artwork metadata |
| POST | `/api/generation/jobs` | optional | Create generation job |
| GET | `/api/generation/jobs/{jobId}` | optional | Poll status |
| POST | `/api/generation/jobs/{jobId}/cancel` | owner | Cancel queued/running job |
| GET | `/api/candidates/{candidateId}` | optional | Candidate detail |
| GET | `/api/candidates/{candidateId}/geojson` | optional | Candidate preview geometry |
| POST | `/api/routes` | optional | Promote candidate to route |
| GET | `/api/routes/{routeId}` | optional/owner | Route detail |
| GET | `/api/routes/{routeId}/export/gpx` | optional/owner | GPX download |
| POST | `/api/routes/{routeId}/share` | owner | Create share link |
| GET | `/api/share/{shareId}` | no | Public route view data |
| POST | `/api/favorites` | user | Favorite route |
| DELETE | `/api/favorites/{routeId}` | user | Remove favorite |

### 47.3 Pydantic Schema Sketch

```python
from enum import Enum
from pydantic import BaseModel, Field

class Activity(str, Enum):
    running = "running"
    cycling = "cycling"
    walking = "walking"

class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class GenerationJobCreate(BaseModel):
    city_id: str = Field(min_length=1)
    activity: Activity
    target_distance_km: float = Field(ge=3, le=100)
    difficulty: Difficulty = Difficulty.medium
    artwork_ids: list[str] | None = None
    max_suggestions: int = Field(default=12, ge=1, le=20)
    export_modes: list[str] = Field(default_factory=lambda: ["continuous"])

class ScoreBreakdown(BaseModel):
    fit_score: float = Field(ge=0, le=1)
    shape_similarity_score: float = Field(ge=0, le=1)
    distance_accuracy_score: float = Field(ge=0, le=1)
    road_quality_score: float = Field(ge=0, le=1)
    continuity_score: float = Field(ge=0, le=1)
    elevation_score: float = Field(ge=0, le=1)

class CandidateSummary(BaseModel):
    candidate_id: str
    artwork_id: str
    artwork_name: str
    rank: int
    distance_km: float
    elevation_gain_m: float | None
    scores: ScoreBreakdown
    warnings: list[str]
```

### 47.4 TypeScript Frontend Types

```ts
export type Activity = "running" | "cycling" | "walking";
export type Difficulty = "easy" | "medium" | "hard";
export type JobStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";

export interface CitySuggestion {
  id: string;
  name: string;
  country: string;
  countryCode: string;
  osmId?: number;
  bbox: [number, number, number, number];
  centroid: { lat: number; lon: number };
}

export interface GenerationJobCreate {
  cityId: string;
  activity: Activity;
  targetDistanceKm: number;
  difficulty: Difficulty;
  artworkIds?: string[] | null;
  maxSuggestions: number;
}

export interface CandidateSummary {
  candidateId: string;
  artworkId: string;
  artworkName: string;
  rank: number;
  distanceKm: number;
  elevationGainM?: number | null;
  fitScore: number;
  shapeSimilarityScore: number;
  roadQualityScore: number;
  warnings: string[];
  previewGeoJsonUrl: string;
}
```

### 47.5 Validation Matrix

| Field | Rule | Error |
|---|---|---|
| `cityId` | must exist in DB or be resolvable from provider | `CITY_NOT_FOUND` |
| `activity` | one of `running`, `cycling`, `walking` | `VALIDATION_ERROR` |
| `targetDistanceKm` | 3-100 | `VALIDATION_ERROR` |
| `difficulty` | one of `easy`, `medium`, `hard` | `VALIDATION_ERROR` |
| `artworkIds` | each ID must exist and be enabled | `ARTWORK_NOT_FOUND` |
| `maxSuggestions` | 1-20 | `VALIDATION_ERROR` |

---

## 48. Detailed Generation State Machines

### 48.1 Backend Job State Machine

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> processing: worker starts
    queued --> cancelled: user cancels
    processing --> completed: candidates persisted
    processing --> failed: handled failure
    processing --> cancelled: cooperative cancel
    failed --> [*]
    completed --> [*]
    cancelled --> [*]
```

### 48.2 Progress Stages

| Stage | Percent range | Details |
|---|---:|---|
| `loading_city` | 0-10 | Load city geometry, bbox, CRS |
| `loading_road_graph` | 10-25 | Fetch/cache OSM graph, filter by profile |
| `selecting_artworks` | 25-35 | Determine eligible artwork list |
| `generating_placements` | 35-45 | Road-density grid and anchor selection |
| `fitting_candidates` | 45-70 | Scale/rotation/placement candidate generation |
| `repairing_routes` | 70-85 | Shortest path repair and continuity checks |
| `scoring` | 85-93 | Similarity, distance, road quality scoring |
| `storing_results` | 93-99 | Persist candidates and artifacts |
| `completed` | 100 | Ready |

### 48.3 Frontend UI State Machine

```mermaid
stateDiagram-v2
    [*] --> empty
    empty --> citySelected
    citySelected --> readyToGenerate
    readyToGenerate --> generating
    generating --> suggestionsReady
    generating --> generationFailed
    suggestionsReady --> candidatePreview
    candidatePreview --> exporting
    exporting --> exported
    candidatePreview --> suggestionsReady
    generationFailed --> readyToGenerate
```

### 48.4 Cancellation Rules

- `queued` jobs can be cancelled immediately.
- `processing` jobs should check cancellation between major loops.
- Cancelled jobs must not delete already completed reusable cache artifacts.
- UI must show "Cancelled" and allow creating a new job with changed parameters.

---

## 49. OSM Ingestion and Graph Cache Details

### 49.1 Overpass Query Strategy

For MVP, fetch roads inside a bounding box with a controlled margin:

```overpass
[out:json][timeout:60];
(
  way["highway"](south,west,north,east);
);
out body;
>;
out skel qt;
```

For production, prefer regional extracts and a preprocessing job instead of repeated Overpass calls.

### 49.2 Graph Cache Key

```text
graph:{city_id}:{activity}:{difficulty}:{osm_data_version}:{algorithm_version}
```

The graph cache value should include:

- serialized node table,
- serialized edge table,
- spatial index artifact if practical,
- CRS used for metric calculations,
- source timestamp,
- filtering summary.

### 49.3 Road Graph DB Tables for Cached Graphs

If the implementation stores reusable road graph data in PostGIS, add:

```sql
CREATE TABLE road_graphs (
  id UUID PRIMARY KEY,
  city_id UUID NOT NULL REFERENCES cities(id),
  activity TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT,
  node_count INTEGER NOT NULL,
  edge_count INTEGER NOT NULL,
  bbox GEOMETRY(Polygon, 4326) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE road_nodes (
  id UUID PRIMARY KEY,
  graph_id UUID NOT NULL REFERENCES road_graphs(id) ON DELETE CASCADE,
  osm_node_id BIGINT,
  point GEOMETRY(Point, 4326) NOT NULL,
  point_projected GEOMETRY(Point),
  degree INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE road_edges (
  id UUID PRIMARY KEY,
  graph_id UUID NOT NULL REFERENCES road_graphs(id) ON DELETE CASCADE,
  from_node_id UUID NOT NULL REFERENCES road_nodes(id),
  to_node_id UUID NOT NULL REFERENCES road_nodes(id),
  osm_way_id BIGINT,
  directed BOOLEAN NOT NULL DEFAULT false,
  geometry GEOMETRY(LineString, 4326) NOT NULL,
  geometry_projected GEOMETRY(LineString),
  length_m DOUBLE PRECISION NOT NULL,
  highway TEXT,
  surface TEXT,
  access TEXT,
  bicycle TEXT,
  foot TEXT,
  oneway TEXT,
  base_weight DOUBLE PRECISION NOT NULL,
  profile_weight DOUBLE PRECISION NOT NULL,
  penalty_breakdown JSONB NOT NULL DEFAULT '{}',
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_road_nodes_point ON road_nodes USING GIST (point);
CREATE INDEX idx_road_edges_geometry ON road_edges USING GIST (geometry);
CREATE INDEX idx_road_edges_graph ON road_edges (graph_id);
```

### 49.4 Graph Simplification

Graph simplification should:

1. Preserve intersections.
2. Preserve dead ends because dead ends may be useful for drawing but penalized.
3. Merge degree-2 chains into longer edges only if geometry is preserved.
4. Preserve original OSM way tags in edge metadata.
5. Avoid simplification that hides stairs, bridges, tunnels, or access changes.

---

## 50. Routing Profile Penalty Tables

### 50.1 Running Penalties

| OSM condition | Multiplier / penalty |
|---|---:|
| `highway=footway/path/pedestrian` | 0.85 |
| `highway=residential/living_street` | 1.00 |
| `highway=service` | 1.15 |
| `highway=tertiary` | 1.35 |
| `highway=primary/secondary` | 2.00 |
| `highway=steps` | 1.35 easy, 1.10 medium/hard |
| `surface=asphalt/paved` | 0.95 |
| `surface=gravel/ground` | 1.15 |
| `access=private` | +500 m equivalent |
| `foot=no` | hard reject |
| `access=no` | hard reject |

### 50.2 Cycling Penalties

| OSM condition | Multiplier / penalty |
|---|---:|
| `highway=cycleway` | 0.70 |
| `bicycle=designated` | 0.75 |
| `highway=residential` | 1.00 |
| `highway=tertiary` with cycle tag | 1.10 |
| `highway=primary/secondary` without cycle tag | 2.50 |
| `highway=footway/path` without bicycle tag | 3.00 or reject by difficulty |
| `highway=steps` | hard reject |
| wrong-way one-way | +1000 m equivalent or reject |
| `surface=gravel` | 1.30, or 2.00 for road-bike mode |
| `bicycle=no` | hard reject |

### 50.3 Walking Penalties

| OSM condition | Multiplier / penalty |
|---|---:|
| `highway=footway/pedestrian/path` | 0.80 |
| `highway=steps` | 0.95 easy disabled only if accessibility option exists |
| `highway=residential` | 1.05 |
| `highway=service` | 1.15 |
| `highway=primary/secondary` | 2.25 |
| `foot=no` | hard reject |
| `access=private` | +500 m equivalent |

### 50.4 Difficulty Modifiers

| Difficulty | Effect |
|---|---|
| Easy | Higher safety penalty, higher elevation penalty, lower turn density, stricter detour ratio |
| Medium | Balanced defaults |
| Hard | Allows more complex roads, higher elevation, tighter turns, rougher surfaces |

---

## 51. Detailed Auto-Fit Algorithm

### 51.1 Inputs

```text
City:
  boundary polygon or bbox
  centroid
  projected CRS

Request:
  activity
  target distance
  difficulty
  optional artwork list

Artwork:
  normalized polyline(s)
  complexity
  recommended distance
  anchor points

Road graph:
  nodes
  edges
  spatial index
  profile weights
```

### 51.2 Candidate Pruning

Before expensive routing:

1. Reject artwork if target distance is outside `recommended_min_km * 0.5` and `recommended_max_km * 2.0`.
2. Reject placement if transformed artwork bbox is mostly outside city boundary.
3. Reject placement if road density near bbox is below threshold.
4. Reject point snapping if too many sample points exceed tolerance.
5. Reject if estimated route distance cannot plausibly meet target.

### 51.3 Road Density Grid

Build grid cells over city boundary:

```pseudo
cell_size_m = clamp(target_distance_km * 100, 300, 1500)
for each cell:
  road_length = sum(edge.length_m intersects cell)
  intersection_count = count(nodes degree >= 3 inside cell)
  barrier_penalty = river/rail/highway barrier estimate
  density_score = normalize(road_length) + normalize(intersection_count) - barrier_penalty
select top cells as placement anchors
```

### 51.4 Detailed Pseudo-Code

```pseudo
function generate_suggestions(request):
  city = load_city(request.city_id)
  crs = select_projected_crs(city.centroid)
  graph = load_or_build_graph(city, request.activity, request.difficulty, crs)
  artworks = select_eligible_artworks(request, city, graph)
  anchors = build_density_anchors(city, graph, request.target_distance_km)

  candidate_heap = MinHeap(max_size = request.max_suggestions * 4)

  for artwork in artworks:
    source_polyline = normalize_and_sample(artwork)
    scales = estimate_scale_candidates(source_polyline, request.target_distance_km, graph)
    rotations = rotation_candidates(artwork)

    for anchor in anchors:
      for scale in scales:
        for rotation in rotations:
          target = transform(source_polyline, anchor, scale, rotation, crs)
          if not cheap_geometry_prefilter(target, city, graph):
            continue

          snap_result = snap_polyline(target, graph)
          if not snap_result.acceptable:
            record_rejection("snap_failed")
            continue

          route_result = repair_and_route(snap_result, graph, request.activity)
          if not route_result.acceptable:
            record_rejection("repair_failed")
            continue

          score = score_route(target, route_result, request)
          if score.fit_score >= minimum_score_threshold:
            candidate_heap.push(candidate(score, target, route_result))

  candidates = rank_and_diversify(candidate_heap.items)
  persist(candidates)
  return candidates
```

### 51.5 Diversification

Do not return 12 near-identical heart candidates. After scoring:

1. Sort by fit score.
2. Keep the best candidate per artwork.
3. If fewer than requested, allow second candidate per artwork only if placement differs materially.
4. Prefer diversity across categories when scores are close.

### 51.6 Minimum Quality Gates

Reject candidates when:

- `shape_similarity_score < 0.45`,
- distance error exceeds 25%,
- route has no continuous path in continuous mode,
- more than 20% of snapped points exceed max snap distance,
- route uses hard-rejected OSM tags,
- route geometry is empty or self-corrupted,
- GPX cannot be generated.

---

## 52. Snapping and Repair Details

### 52.1 Sampling Strategy

Use adaptive sampling:

- sample more densely around curves,
- preserve sharp corners,
- avoid too many points for simple lines,
- target 100-300 sampled points for MVP shapes.

Sharp corners must be tagged as keypoints so similarity scoring can verify they survive routing.

### 52.2 Nearest Edge Search

For each sample:

```pseudo
candidate_edges = spatial_index.query(buffer(point, tolerance))
rank by:
  projected_distance_to_edge
  edge_profile_weight
  edge_heading_similarity_to_target_segment
  access legality
select best edge
```

### 52.3 Heading Similarity

When snapping a point on a segment, prefer roads aligned with the target segment:

```text
heading_penalty = abs(angle_difference(target_heading, edge_heading)) / 180
```

This prevents a nearby perpendicular road from being selected when a slightly farther parallel road is better.

### 52.4 Repair Routing Weight

When routing between snapped points, use:

```text
repair_weight =
  edge.profile_weight
+ distance_from_target_segment_penalty
+ heading_penalty
+ duplicate_edge_penalty
```

The route should not simply find the shortest path; it should stay visually close to the artwork.

### 52.5 Duplicate Edge Handling

Repeated edges are sometimes necessary but should be penalized.

Rules:

- allow exact duplicate edge only if no alternative exists,
- penalize repeated segments after first use,
- detect backtracking patterns A-B then B-A,
- expose warning if more than 10% of route length is repeated.

---

## 53. Shape Similarity Metric Details

### 53.1 Metric Normalization

All similarity metrics must compare normalized geometries:

1. Project both target and generated route to metric CRS.
2. Resample both to equal-length point sequences if needed.
3. Normalize translation and scale for shape-only comparison.
4. Keep original distance for distance score separately.

### 53.2 Hausdorff Component

```text
hausdorff_score = 1 - clamp(hausdorff_distance / allowed_shape_error_m, 0, 1)
```

Allowed shape error:

```text
allowed_shape_error_m = max(50, target_distance_m * 0.015)
```

### 53.3 Turning Angle Component

Compute turning angles at keypoints:

```text
turning_score = 1 - average(abs(target_angle_i - route_angle_i)) / 180
```

Use dynamic time warping if the route has more points than the target.

### 53.4 Bounding Box Component

```text
aspect_score = 1 - min(abs(target_aspect - route_aspect) / target_aspect, 1)
```

### 53.5 Combined Shape Similarity

```text
shape_similarity_score =
  0.45 * hausdorff_score
+ 0.25 * average_distance_score
+ 0.20 * turning_score
+ 0.10 * aspect_score
```

For text or symbol-like shapes, increase turning score weight.

---

## 54. GPX and Export Implementation Details

### 54.1 GPX Metadata

Include:

- route name,
- description,
- creator,
- generation timestamp,
- city,
- activity,
- target distance,
- actual distance,
- export mode.

Example metadata extension:

```xml
<metadata>
  <name>Budapest Heart 10K Running</name>
  <desc>Generated by CityShapeRunner. Activity: running. Distance: 10.18 km.</desc>
</metadata>
```

### 54.2 Trackpoint Rules

- Coordinates must be WGS84 latitude/longitude.
- Use 6 decimal places for coordinates.
- Keep point order.
- Remove exact duplicate consecutive points.
- Preserve enough detail for route shape.
- Do not include timestamps by default; users import as planned routes, not completed activities.

### 54.3 Elevation

MVP can omit elevation. If included:

- use a configured elevation provider,
- cache elevation samples,
- never block GPX export if elevation provider fails,
- set `elevation_gain_m` to null when unavailable.

### 54.4 Export Modes UI Copy

Continuous:

> Follows real roads and paths. Best for Garmin, Komoot, and normal navigation.

Connect-the-dots:

> Contains only key points. Use this only if you intentionally plan to pause/resume GPS recording to draw straight virtual lines.

---

## 55. UI/UX Screen-by-Screen Specification

### 55.1 Landing Page

Sections:

1. Hero with city search.
2. Three-step explanation.
3. Example generated routes.
4. Supported exports/devices.
5. Market differentiator: city-specific suggestions.

Hero copy:

> Generate GPS art routes from any city. Choose a city, activity, and distance; download a GPX route ready for your watch.

Primary CTA:

- "Create GPS Art"

### 55.2 Studio Control Panel

Fields:

- City search input.
- Activity segmented control.
- Distance slider and numeric input.
- Difficulty selector.
- Optional artwork category filter.
- Generate button.

Validation:

- Generate disabled until city selected.
- Distance invalid values show inline error.
- If activity is cycling and distance < 8 km, show warning that cycling artwork may need more distance.

### 55.3 Generation Progress

Display:

- spinner/progress bar,
- current stage,
- friendly explanation,
- cancel button.

Stage messages:

| Stage | Message |
|---|---|
| loading_road_graph | "Loading streets, paths, and cycleways..." |
| selecting_artworks | "Choosing shapes that fit this city and distance..." |
| fitting_candidates | "Testing rotations, sizes, and placements..." |
| repairing_routes | "Connecting the route along real roads..." |
| scoring | "Ranking the best-looking routes..." |

### 55.4 Suggestion Grid

Each card:

- artwork preview,
- name,
- distance,
- fit score,
- activity badge,
- warning icon if any,
- "Preview" button.

Sort:

1. valid high-score candidates,
2. city-signature candidates,
3. fallback simple shapes.

### 55.5 Route Preview

Map layers:

- base map,
- generated route,
- target artwork ghost overlay,
- start/finish markers,
- warning segments if any.

Side panel:

- title,
- score breakdown,
- distance,
- elevation,
- warnings,
- export buttons,
- share/save buttons.

### 55.6 Empty States

No city selected:

> Search for a city to start generating GPS art.

No suggestions:

> We could not find a good route for these settings. Try a longer distance, Running mode, or a simpler shape.

### 55.7 Accessibility Details

- Map must not be the only way to understand route metadata.
- All buttons need accessible names.
- Suggestion cards must be keyboard selectable.
- Progress updates should use polite ARIA live region.

---

## 56. Frontend Component Contracts

### 56.1 `CitySearchInput`

Props:

```ts
interface CitySearchInputProps {
  value: CitySuggestion | null;
  onChange(city: CitySuggestion | null): void;
  countryCode?: string;
  disabled?: boolean;
}
```

Behavior:

- debounce input by 300 ms,
- show loading state,
- allow keyboard navigation,
- persist last selected city in local storage.

### 56.2 `GenerationProgress`

Props:

```ts
interface GenerationProgressProps {
  status: JobStatus;
  stage?: string;
  percent: number;
  onCancel?: () => void;
}
```

Behavior:

- if status failed, show error component instead,
- if percent stalls, keep polling but show "Still working..." after 20 seconds.

### 56.3 `RouteMap`

Props:

```ts
interface RouteMapProps {
  city?: CitySuggestion;
  routeGeoJson?: GeoJSON.FeatureCollection;
  targetGeoJson?: GeoJSON.FeatureCollection;
  selectedCandidateId?: string;
  warnings?: RouteWarning[];
}
```

Behavior:

- fit bounds when candidate changes,
- preserve manual zoom after user interaction unless new city selected,
- render route above artwork overlay,
- show start and finish markers.

---

## 57. Backend Service Interfaces

### 57.1 City Service

```python
class CityService:
    async def search(self, query: str, country: str | None) -> list[CitySuggestion]:
        ...

    async def resolve(self, city_id: str) -> City:
        ...

    async def ensure_boundary(self, city: City) -> City:
        ...
```

### 57.2 Graph Service

```python
class RoadGraphService:
    async def load_or_build(
        self,
        city: City,
        activity: Activity,
        difficulty: Difficulty,
        crs: str,
    ) -> RoadGraph:
        ...
```

### 57.3 Generation Service

```python
class GenerationService:
    async def create_job(self, request: GenerationJobCreate, user: User | None) -> GenerationJob:
        ...

    async def get_job(self, job_id: UUID, user: User | None) -> GenerationJobDetail:
        ...
```

### 57.4 Worker Runner

```python
class GenerationWorker:
    async def run_job(self, job_id: UUID) -> None:
        ...

    async def update_progress(self, job_id: UUID, stage: str, percent: int) -> None:
        ...
```

---

## 58. Detailed Test Fixtures

### 58.1 Mini Grid City

Purpose:

- deterministic shape fitting,
- easy heart/star route,
- tests road snapping and distance.

Graph:

- 10x10 grid,
- 100 m spacing,
- all residential,
- no access restrictions.

Expected:

- heart 3 km route generates successfully,
- star route generates successfully,
- cycling and running produce similar results.

### 58.2 River City

Purpose:

- tests barriers and connect-the-dots recommendation.

Graph:

- two dense grids separated by river,
- two bridge edges,
- target shape crossing river multiple times.

Expected:

- continuous mode penalizes excessive bridge detours,
- connect-the-dots mode warning is suggested,
- generated route never crosses river except bridge in continuous mode.

### 58.3 Restricted Area City

Purpose:

- tests `access=no`, `private`, and route safety.

Expected:

- `access=no` edges never appear,
- `access=private` edges only appear with warning and penalty if not hard-rejected,
- route quality score decreases.

### 58.4 Organic Hungarian City Fixture

Purpose:

- tests irregular roads and lower shape similarity.

Expected:

- simple shapes score higher than complex ones,
- distance recommendations prefer 8-20 km for recognizable shapes,
- failure messages suggest longer distance for too-small requests.

---

## 59. Acceptance Test Matrix

| Scenario | Input | Expected |
|---|---|---|
| Generate Budapest heart | Budapest, running, 10 km, medium | at least one valid candidate, GPX export |
| Cycling rejects stairs | fixture with stairs, cycling | no stair edges in route |
| Running allows stairs | fixture with stairs, running | stairs allowed with penalty |
| Private road warning | route uses private edge | warning present, score reduced |
| No city found | invalid city query | clear empty state |
| Too-short cycling route | cycling 3 km complex shape | no candidate or low-score warning |
| GPX continuous export | valid candidate | GPX has dense trackpoints |
| GPX connect-the-dots | valid candidate | GPX has only keypoints |
| Job cancellation | cancel queued job | status cancelled |
| Idempotent request | same request twice | same completed job returned or cache hit indicated |

---

## 60. Docker Compose Detail

Minimum local services:

```yaml
services:
  web:
    build: ./apps/web
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000

  api:
    build: ./apps/api
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/cityshape
      REDIS_URL: redis://redis:6379/0

  worker:
    build: ./apps/worker
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/cityshape
      REDIS_URL: redis://redis:6379/0

  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: cityshape
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
```

---

## 61. CI/CD Requirements

### 61.1 CI Checks

Every pull request must run:

- frontend type check,
- frontend unit tests,
- backend unit tests,
- geometry/routing tests,
- GPX validation tests,
- API schema generation check,
- Docker build smoke test if feasible.

### 61.2 Test Isolation

CI must not depend on:

- live Overpass,
- live Nominatim,
- live OSRM,
- paid map APIs.

Use:

- fixture OSM files,
- mocked geocoder responses,
- local mini routing graph.

### 61.3 Release Steps

1. Run migrations.
2. Deploy API.
3. Deploy worker.
4. Deploy web.
5. Run readiness checks.
6. Run smoke generation against a fixture city.
7. Verify GPX download.

---

## 62. Data Retention and Privacy Detail

### 62.1 Anonymous Data

Anonymous routes:

- may be stored for 30 days by default,
- should be deletable by cleanup job,
- should not include user identity,
- should use opaque IDs.

### 62.2 Registered User Data

Registered saved routes:

- stored until user deletes them,
- private by default,
- export files regenerated or retained according to storage policy.

### 62.3 Public Share Links

Share links:

- use random high-entropy IDs,
- can be revoked by owner,
- expose route geometry and metadata,
- must not expose owner email unless user explicitly opts in.

---

## 63. Feature Flags

Recommended flags:

| Flag | Default | Purpose |
|---|---|---|
| `ENABLE_CONNECT_THE_DOTS_EXPORT` | true | Optional GPX mode |
| `ENABLE_CUSTOM_SVG_UPLOAD` | false | v1 feature |
| `ENABLE_USER_ACCOUNTS` | false for MVP | Auth rollout |
| `ENABLE_ELEVATION` | false | Optional provider dependency |
| `ENABLE_AI_RECOMMENDATIONS` | false | Future AI ranking |
| `ENABLE_PUBLIC_GALLERY` | false | Future social feature |
| `ENABLE_HIGH_QUALITY_SEARCH` | false | Longer worker search budget |

---

## 64. Implementation Quality Bar

### 64.1 Route Generation Quality

Do not mark a route candidate as valid unless:

- it has non-empty geometry,
- it has at least 2 trackpoints,
- continuous mode is graph-connected,
- distance is computed from geometry,
- hard-rejected OSM tags are absent,
- score breakdown is present,
- route can be serialized to GeoJSON and GPX.

### 64.2 Code Quality

- Keep algorithm modules pure where practical.
- Avoid provider-specific logic leaking into domain services.
- Use typed DTOs and schemas.
- Store units in variable names (`distance_km`, `length_m`).
- Avoid magic constants; centralize algorithm parameters.
- Include comments only for non-obvious GIS/math decisions.

### 64.3 Documentation Quality

Repository docs must include:

- local setup,
- provider configuration,
- how to seed cities/artwork,
- how to run fixture generation,
- GPX export explanation,
- known limitations.

---

## 65. Detailed MVP Build Order for CLI AI Agents

Use this order to reduce implementation risk:

1. Create monorepo and Docker Compose.
2. Add PostGIS migrations for users, cities, artworks, generation jobs, candidates, routes.
3. Seed artwork metadata and simple SVG files.
4. Seed Hungarian cities with static bbox/centroid.
5. Implement frontend studio with mocked API.
6. Implement FastAPI health, city, artwork endpoints.
7. Implement generation job create/status with fake worker.
8. Implement GPX generator from a hardcoded LineString.
9. Add GPX unit tests.
10. Implement SVG-to-polyline parser.
11. Add geometry unit tests.
12. Implement fixture graph loader.
13. Implement nearest-edge snapping on fixture graph.
14. Implement shortest-path repair on fixture graph.
15. Implement candidate scoring.
16. Connect worker to generate fixture-based candidates.
17. Replace fixture city path with OSM graph adapter behind interface.
18. Add route preview GeoJSON endpoint.
19. Connect frontend map preview.
20. Add GPX download from selected candidate.
21. Add rate limits.
22. Add cache/idempotency by request hash.
23. Add Playwright E2E happy path.
24. Add Docker smoke test.
25. Only then add optional auth/save/share.

---

## 66. Final Implementation Note

The most important engineering decision is to avoid promising universal city-shape discovery in the first release. The product should feel automatic by combining a strong artwork library, deterministic Auto-Fit, road-aware snapping, robust scoring, and city-signature recommendation logic. This approach is implementable by a CLI AI coding agent, commercially useful, and extensible toward future AI-driven shape generation and deeper graph-pattern discovery.
