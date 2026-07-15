"""initial schema with PostGIS

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00
"""
from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "postgis"')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            email TEXT UNIQUE,
            display_name TEXT,
            avatar_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            country TEXT NOT NULL,
            country_code TEXT NOT NULL,
            osm_id BIGINT,
            osm_type TEXT,
            centroid GEOGRAPHY(Point, 4326) NOT NULL,
            bbox GEOMETRY(Polygon, 4326),
            boundary GEOMETRY(MultiPolygon, 4326),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_cities_normalized_name ON cities (normalized_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cities_centroid ON cities USING GIST (centroid)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cities_boundary ON cities USING GIST (boundary)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS artworks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            complexity TEXT NOT NULL,
            svg_path TEXT NOT NULL,
            aspect_ratio DOUBLE PRECISION NOT NULL,
            recommended_min_km DOUBLE PRECISION NOT NULL,
            recommended_max_km DOUBLE PRECISION NOT NULL,
            default_sample_count INTEGER NOT NULL DEFAULT 200,
            is_city_featured BOOLEAN NOT NULL DEFAULT false,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_artworks_category ON artworks (category)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_artworks_recommended_distance "
        "ON artworks (recommended_min_km, recommended_max_km)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_jobs (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id),
            city_id TEXT NOT NULL REFERENCES cities(id),
            status TEXT NOT NULL,
            activity TEXT NOT NULL,
            target_distance_km DOUBLE PRECISION NOT NULL,
            difficulty TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            error_code TEXT,
            error_message TEXT,
            progress_stage TEXT,
            progress_percent INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_jobs_request_hash ON generation_jobs (request_hash)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs (status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS route_candidates (
            id TEXT PRIMARY KEY,
            job_id UUID NOT NULL REFERENCES generation_jobs(id) ON DELETE CASCADE,
            artwork_id TEXT NOT NULL REFERENCES artworks(id),
            rank INTEGER,
            status TEXT NOT NULL,
            route_geometry GEOMETRY(LineString, 4326),
            target_geometry GEOMETRY(LineString, 4326),
            distance_km DOUBLE PRECISION,
            elevation_gain_m DOUBLE PRECISION,
            fit_score DOUBLE PRECISION,
            shape_similarity_score DOUBLE PRECISION,
            distance_accuracy_score DOUBLE PRECISION,
            road_quality_score DOUBLE PRECISION,
            elevation_score DOUBLE PRECISION,
            continuity_score DOUBLE PRECISION,
            dead_end_penalty DOUBLE PRECISION,
            placement JSONB NOT NULL DEFAULT '{}',
            warnings JSONB NOT NULL DEFAULT '[]',
            debug JSONB NOT NULL DEFAULT '{}',
            keypoint_geojson JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_route_candidates_job_rank ON route_candidates (job_id, rank)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_route_candidates_route_geometry ON route_candidates USING GIST (route_geometry)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_routes (
            id TEXT PRIMARY KEY,
            user_id UUID REFERENCES users(id),
            candidate_id TEXT REFERENCES route_candidates(id),
            city_id TEXT NOT NULL REFERENCES cities(id),
            artwork_id TEXT NOT NULL REFERENCES artworks(id),
            artwork_name TEXT NOT NULL,
            activity TEXT NOT NULL,
            distance_km DOUBLE PRECISION NOT NULL,
            elevation_gain_m DOUBLE PRECISION,
            route_geometry GEOMETRY(LineString, 4326) NOT NULL,
            keypoint_geojson JSONB,
            scores JSONB NOT NULL DEFAULT '{}',
            warnings JSONB NOT NULL DEFAULT '[]',
            gpx_storage_key TEXT,
            visibility TEXT NOT NULL DEFAULT 'private',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS route_exports (
            id UUID PRIMARY KEY,
            route_id TEXT NOT NULL REFERENCES generated_routes(id) ON DELETE CASCADE,
            export_type TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            file_name TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS share_links (
            id TEXT PRIMARY KEY,
            route_id TEXT NOT NULL REFERENCES generated_routes(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS road_graphs (
            id UUID PRIMARY KEY,
            city_id TEXT NOT NULL REFERENCES cities(id),
            activity TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            source TEXT NOT NULL,
            source_version TEXT,
            node_count INTEGER NOT NULL,
            edge_count INTEGER NOT NULL,
            bbox GEOMETRY(Polygon, 4326) NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    for table in (
        "road_graphs", "share_links", "route_exports", "generated_routes",
        "route_candidates", "generation_jobs", "artworks", "cities", "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
