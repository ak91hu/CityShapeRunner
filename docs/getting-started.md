# Getting started

## Prerequisites

- Python 3.13+
- Node.js 20+
- npm 10+
- (Optional) PostgreSQL 16+ with PostGIS
- (Optional) Docker & Docker Compose

## Backend setup

```bash
cd pathforge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Generate shape SVGs (required for shape matching)
python scripts/generate_shapes.py

# Seed the database with cities and artworks
python scripts/seed.py

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

OpenAPI docs at `http://localhost:8000/docs`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:3000`.

## Optional: OpenRouteService

For real-road-snapped geometry (instead of synthetic grid), set an ORS API key:

```bash
# Windows PowerShell
$env:CSR_ORS_API_KEY = "your-api-key"
```

Or add it to a `.env` file in the project root:

```
CSR_ORS_API_KEY=your-api-key
```

You can obtain a free key at [openrouteservice.org](https://openrouteservice.org).

## Optional: Database

By default the app uses an in-memory SQLite store. For persistence:

```bash
# Run with PostgreSQL
docker compose up -d db
alembic upgrade head
```

## Docker Compose (everything at once)

```bash
docker compose up --build
```

This starts the API, frontend, and PostgreSQL database together.

## Verify it works

```bash
# Health check
curl http://localhost:8000/api/health

# List cities
curl http://localhost:8000/api/cities

# Generate a route
curl -X POST http://localhost:8000/api/generation/generate \
  -H "Content-Type: application/json" \
  -d '{"city_id":"budapest","artwork_id":"heart","activity":"running","distance_km":8.0}'
```

## Running tests

```bash
python -m pytest              # All tests
python -m pytest -q           # Quiet mode
python -m pytest -x           # Stop on first failure
python -m pytest tests/unit   # Unit tests only
python -m pytest tests/api    # API/integration tests only
```
