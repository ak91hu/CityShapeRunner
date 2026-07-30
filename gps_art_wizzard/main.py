"""FastAPI entry point for GPS Art Wizard."""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .logging_config import (
    bind_request_id,
    configure_logging,
    reset_request_id,
)

configure_logging()
log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="GPS Art Wizard",
        description="Generate and evaluate GPS-art route candidates from natural-language prompts. "
        "Road matching requires a configured routing provider, and every result must be reviewed "
        "for local access, safety, and current conditions before use.",
        version="0.1.0",
    )
    origins = os.getenv("WEB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        supplied_id = request.headers.get("x-request-id", "").strip()
        request_id = (
            supplied_id
            if supplied_id
            and len(supplied_id) <= 80
            and all(char.isalnum() or char in "._:-" for char in supplied_id)
            else uuid.uuid4().hex
        )
        token = bind_request_id(request_id)
        started = time.perf_counter()
        request_log = log.debug if request.url.path == "/health" else log.info
        request_log(
            "HTTP request started",
            extra={
                "event": "http.request.started",
                "method": request.method,
                "path": request.url.path,
            },
        )
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            response.headers["X-Request-ID"] = request_id
            request_log(
                "HTTP request completed",
                extra={
                    "event": "http.request.completed",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            log.exception(
                "HTTP request failed",
                extra={
                    "event": "http.request.failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000.0,
                        2,
                    ),
                },
            )
            raise
        finally:
            reset_request_id(token)

    app.include_router(router)

    # Serve the built SPA (frontend/dist) at / when present. Routes registered
    # above (/health, /generate, /docs) take precedence over this catch-all.
    spa_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if spa_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(spa_dir), html=True), name="spa")
    return app


app = create_app()


def run() -> None:
    """Console-script entrypoint: ``gps-art-wizzard``."""
    import uvicorn

    host = os.getenv("API_HOST", "127.0.0.1")
    port_value = os.getenv("PORT") or os.getenv("API_PORT") or "8000"
    port = int(port_value)
    uvicorn.run(
        "gps_art_wizzard.main:app",
        host=host,
        port=port,
        reload=False,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    run()
