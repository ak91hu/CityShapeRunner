# CityShapeRunner — Documentation

CityShapeRunner is a GPS art generation platform. It takes an SVG shape and a
city, and produces a GPX route that follows real streets while tracing that
shape — ready to load onto a Garmin, Strava, or Komoot.

## How it works

1. **Pick a shape** — hearts, stars, animals, landmarks, and more (150+ curated
   SVGs).
2. **Pick a city** — 56 Hungarian cities with analysed road networks.
3. **Generate** — the engine evaluates thousands of placements, rotations, and
   scales; matches the shape to real streets via beam search; and returns
   ranked route candidates.
4. **Export** — download a `continuous` (dense trackpoints) or `connect-the-dots`
   GPX file.

## Key design decisions

| Decision | Rationale |
|---|---|
| SVG-first, not image-based | Vectors preserve sharp corners and scale cleanly |
| Graph-based matching | Roads are a graph — beam search over graph nodes |
| City-specific road graphs | Different densities suit different activities (run, cycle, walk) |
| Corridor scoring + beam search | Fast rejection of bad fits before expensive route construction |
| AI-assisted retry | Low-confidence results can request LLM refinement |

## Core stack

- **Backend** — Python 3.13+, FastAPI, Uvicorn
- **Geometry engine** — Shapely, OSMnx, NetworkX
- **Frontend** — Next.js 15 (App Router), TypeScript, Leaflet, Tailwind CSS
- **Database** — SQLite (dev), PostgreSQL/PostGIS (prod)
- **Map data** — OpenStreetMap via OSMnx + OpenRouteService
- **Build** — Docker Compose, Alembic

## Quick start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

See [Getting started](getting-started.md) for the full guide.

---

*CityShapeRunner — OpenStreetMap contributors*
