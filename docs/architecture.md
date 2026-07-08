# Architecture

## Monorepo layout

```
pathforge/
├── app/                    # Backend (FastAPI)
│   ├── api/                # Route handlers
│   │   ├── routers/        # /api/cities, /api/artworks, /api/generation, ...
│   │   └── deps.py         # DI helpers
│   ├── core/               # Domain logic
│   │   ├── shape_matching.py  # SVG → street matching (core algorithm)
│   │   ├── generation.py     # Orchestration / worker
│   │   ├── graph.py          # Road graph construction
│   │   ├── geometry.py       # SVG anchor extraction, transforms
│   │   ├── scoring.py        # Route quality scoring
│   │   ├── gpx.py            # GPX 1.1 serialization
│   │   ├── units.py          # Projection / coordinate helpers
│   │   └── ors_client.py     # OpenRouteService snap-to-road
│   ├── models.py           # Pydantic / SQLModel schemas
│   ├── stores.py           # In-memory / DB stores
│   ├── services.py         # Rate limiter, background worker
│   ├── config.py           # App settings (env-based)
│   ├── graph_provider.py   # Lazy city-graph loader
│   ├── main.py             # FastAPI entrypoint
│   └── seed.py             # Seed data access
├── data/                   # Data files
│   ├── shapes/             # Generated SVG files (150+)
│   ├── seed/               # Seed data JSON
│   └── cache/              # LRU-cached city graphs
├── frontend/               # Next.js 15 App Router
│   ├── app/                # Pages & layouts
│   ├── components/         # Reusable UI components
│   └── lib/                # API client, types, i18n
├── docs/                   # MkDocs documentation
├── scripts/                # Utilities
│   ├── generate_shapes.py  # SVG file generator
│   └── seed.py             # Database seeder
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   └── api/                # Integration tests
├── infrastructure/         # Docker, CI/CD
└── alembic/                # DB migrations
```

## System architecture (C4 Level 1)

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Browser    │────▶│   FastAPI App   │────▶│  PostgreSQL  │
│  (Next.js)   │     │   (Uvicorn)     │     │  + PostGIS   │
└──────────────┘     └─────────────────┘     └──────────────┘
                           │
                    ┌──────┴──────┐
                    │    Redis    │  (rate limits, cache)
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  ORS API    │  (snap-to-road)
                    └─────────────┘
```

## Request flow: generation

1. `POST /api/generation/generate` — accepts `(city_id, artwork_id, activity, distance_km)`
2. Worker picks up the job, updates status to `processing`
3. **SVG parsing** — the artwork SVG is loaded and decomposed into a weighted shape graph (polylines + control points)
4. **City suitability** — the engine estimates whether the shape fits the city's road network dimensions
5. **Anchor generation** — control points are extracted and assigned weights
6. **Transform enumeration** — multiple scale/rotation/placement combinations are generated
7. **Corridor scoring** — each transform is quickly rejected or accepted based on road alignment
8. **Beam matching** — accepted transforms are matched to the road graph via beam search
9. **Route construction** — matched segments are connected into a continuous route
10. **Refinement** — top candidates are refined for distance accuracy
11. **Scoring** — each candidate is scored on shape fidelity, distance accuracy, and route quality
12. **ORS snap** — if an ORS key is configured, the route is snapped to real roads
13. **GPX export** — top candidate is serialized to GPX 1.1 (continuous + dots)
14. **Job completion** — status set to `completed` with results

## Key architectural decisions

- **In-memory store by default** — zero-dependency startup for development; pluggable DB backend for production
- **Lazy graph loading** — city road graphs are built on first access and cached (LRU)
- **Background worker** — generation runs on a thread pool so the API stays responsive
- **Rate limiting** — per-client-IP limits on generation, GPX download, and search
- **SVG as source of truth** — shapes are defined as SVG paths, not raster images; this preserves sharp angles and scales arbitrarily
