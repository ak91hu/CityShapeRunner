from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import install_error_handlers
from app.api.routers import (
    artworks,
    candidates,
    cities,
    generation,
    health,
    routes,
    share,
)
from app.config import get_settings

app = FastAPI(
    title="CityShapeRunner API",
    version="1.0.0",
    description="Automated GPS-art route generator (CityShapeRunner / CityArtGPX)",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_web_url, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_routers = [health, cities, artworks, generation, candidates, routes, share]
for r in api_routers:
    app.include_router(r.router, prefix="/api")

install_error_handlers(app)

shapes_dir = Path(settings.data_dir) / "shapes"
if shapes_dir.exists():
    app.mount("/assets/shapes", StaticFiles(directory=str(shapes_dir)), name="shapes")

docs_site = Path(__file__).resolve().parent.parent / "site"
if docs_site.exists():
    app.mount("/documentation", StaticFiles(directory=str(docs_site), html=True), name="docs")


@app.get("/")
async def root() -> dict:
    return {"name": "CityShapeRunner", "version": "1.0.0", "docs": "/docs", "health": "/api/health"}
