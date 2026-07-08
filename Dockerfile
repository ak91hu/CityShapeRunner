# ---- Stage 1: Build Next.js ----
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Stage 2: Python backend + runtime ----
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
    NODE_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Next.js runtime
COPY --from=node:20-alpine /usr/local /usr/local

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts
COPY data ./data

# Generate shapes
RUN python scripts/generate_shapes.py

# Frontend build
COPY --from=frontend-builder /build/.next /app/frontend/.next
COPY --from=frontend-builder /build/node_modules /app/frontend/node_modules
COPY --from=frontend-builder /build/package.json /app/frontend/package.json
COPY --from=frontend-builder /build/public /app/frontend/public
COPY --from=frontend-builder /build/next.config.mjs /app/frontend/next.config.mjs

# Startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Nginx config
COPY infrastructure/nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["/app/start.sh"]
