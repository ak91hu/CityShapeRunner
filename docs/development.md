# Development guide

## Code style

- **Python** - formatted with Ruff. Config in `pyproject.toml`.
- **TypeScript / React** - formatted with Prettier. Config in `frontend/.prettierrc`.
- **Imports** - absolute imports preferred (`from app.core import ...`).

Run linting:

```bash
ruff check .
ruff format --check .
```

## Testing

```bash
# Run all tests
python -m pytest

# Unit tests only
python -m pytest tests/unit

# API tests only
python -m pytest tests/api

# With coverage
python -m pytest --cov=app --cov-report=term-missing
```

Test structure:

```
tests/
├── conftest.py             # Shared fixtures (client, mini_grid, budapest)
├── unit/
│   ├── test_graph.py       # Road graph construction
│   ├── test_geometry.py    # SVG anchor extraction
│   ├── test_generation.py  # Core generation pipeline
│   ├── test_scoring.py     # Route scoring
│   └── test_gpx.py         # GPX serialization
└── api/
    └── test_generation_flow.py  # Full API workflow
```

## Adding a new shape

1. Add SVG path data to `scripts/generate_shapes.py` - SHAPES dict
2. Add metadata to `data/seed/artworks.json` - name, category, complexity, tags, city affinities
3. Regenerate SVGs: `python scripts/generate_shapes.py`
4. (Re)seed: `python scripts/seed.py`
5. Verify: check `GET /api/artworks` includes the new shape

## Adding a new city

1. Add the city to `data/seed/cities.json` with centroid coordinates and bounding box
2. Add OSM highway data - the road graph is built on first access via OSMnx
3. (Re)seed: `python scripts/seed.py`
4. Verify: check `GET /api/cities` includes the new city

## Debugging generation

- Set `CSR_MAPBOX_ACCESS_TOKEN` in `.env` to enable mapbox road snapping.
- Enable debug metadata: pass `debug=true` to the generate endpoint
- Check the worker logs - each stage is logged with duration

## Profiling

Slow? Common culprits:

- **Mapbox Directions API calls** - a single request is made to Mapbox containing adaptively reduced waypoints (max 25).
- **Beam search width** - `BEAM_WIDTH = 10` is the default; lowering it speeds up matching
- **City graph size** - large cities (Budapest) have dense road networks; consider `simplify=True` in OSMnx
