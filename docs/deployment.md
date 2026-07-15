# Deployment

## Docker Compose (recommended)

```bash
docker compose up --build -d
```

Services:
- `api` - FastAPI on port 8000
- `frontend` - Next.js on port 3000
- `db` - PostgreSQL 16 + PostGIS

## Manual deployment

### Backend

```bash
# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or with gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend

```bash
cd frontend
npm run build
npm start  # Next.js production server on port 3000
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `CSR_MAPBOX_ACCESS_TOKEN` | No | - | Mapbox Access Token for road snapping |
| `CSR_ZEN_API_KEY` | No | - | Zen API key (AI-assisted retry) |
| `CSR_DATABASE_URL` | No | `sqlite://` | PostgreSQL connection string |
| `CSR_LOG_LEVEL` | No | `INFO` | Logging level |
| `CSR_CORS_ORIGINS` | No | `*` | Allowed CORS origins |

## Database migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Monitoring

- Health endpoint: `GET /api/health`
- API docs: `GET /api/docs`
- Rate limit headers returned on every response: `X-RateLimit-Remaining`, `X-RateLimit-Reset`
