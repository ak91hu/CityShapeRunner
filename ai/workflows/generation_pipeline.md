# Generation Pipeline Workflow

This document explains how the GPS Art Generation pipeline works in `PathForge`.

## 1. Request Lifecycle
1. User submits a request containing `city_id`, `artwork_ids`, `target_distance_km`.
2. `app.services.GenerationService.create_job` handles it, creates a Job ID, and spins up a background worker thread (`app.worker.start_worker`).
3. Client polls `GET /api/generation/jobs/{job_id}` until `status` is `completed` or `failed`.

## 2. Core Generation
- The worker executes `app.core.generation.generate_suggestions`.
- It dynamically fetches the road graph via OSMNx for the city or falls back to synthetic data (`app.graph_provider.city_or_fixture`).
- It uses the shape matching algorithm (Frechet distance, Hausdorf, or custom polygon-fit algorithms) to find matching continuous subgraphs within the road network (`app.core.matcher`).

## 3. Post-Processing & ORS Snapping
- Once raw candidates are found, the algorithm refines the geometry to follow actual road curvatures.
- If `CSR_ORS_API_KEY` is present, it uses `app.core.ors_client.snap_route_to_roads` to query OpenRouteService, snapping the abstract graph nodes to exact real-world street polylines.
- In test environments (`tests/conftest.py`), this step is bypassed to prevent rate-limiting, and raw node coordinates are used.

## 4. Scoring
- The candidates are evaluated based on `fit_score`, `shape_similarity_score`, `road_quality_score`, etc., and sorted by `rank`.

## When Modifying:
- Never break the abstract graph implementation. Ensure your logic works on both the real OSM graph and the fallback synthetic grids.
- Add robust tests in `tests/api/` or `tests/unit/` using fixtures like `mini-grid` to avoid hitting external APIs.
