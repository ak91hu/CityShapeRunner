# syntax=docker/dockerfile:1

FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim-bookworm AS python-build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
ARG INSTALL_EXTRAS=
COPY pyproject.toml ./
COPY docs/README.md ./docs/README.md
COPY gps_art_wizzard/ ./gps_art_wizzard/
RUN if [ -n "${INSTALL_EXTRAS}" ]; then \
        python -m pip install --prefix=/runtime ".[${INSTALL_EXTRAS}]"; \
    else \
        python -m pip install --prefix=/runtime .; \
    fi

FROM python:3.14-slim-bookworm AS runtime
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    OLLAMA_BASE_URL= \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

WORKDIR /app
COPY --from=python-build /runtime/ /usr/local/
COPY --chown=app:app gps_art_wizzard/ ./gps_art_wizzard/
COPY --chown=app:app config/ ./config/
COPY --chown=app:app docs/ ./docs/
COPY --from=frontend-build --chown=app:app /build/frontend/dist/ ./frontend/dist/

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('API_PORT', '8000') + '/health', timeout=2)"
STOPSIGNAL SIGTERM
CMD ["gps-art-wizzard"]
