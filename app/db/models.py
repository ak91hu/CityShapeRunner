from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class City(Base):
    __tablename__ = "cities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(Text, nullable=False)
    osm_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    osm_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    centroid: Mapped[object] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    bbox: Mapped[object | None] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    boundary: Mapped[object | None] = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Artwork(Base):
    __tablename__ = "artworks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    complexity: Mapped[str] = mapped_column(Text, nullable=False)
    svg_path: Mapped[str] = mapped_column(Text, nullable=False)
    aspect_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_min_km: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_max_km: Mapped[float] = mapped_column(Float, nullable=False)
    default_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    is_city_signature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    activity: Mapped[str] = mapped_column(Text, nullable=False)
    target_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    difficulty: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    candidates: Mapped[list["RouteCandidate"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class RouteCandidate(Base):
    __tablename__ = "route_candidates"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    artwork_id: Mapped[str] = mapped_column(ForeignKey("artworks.id"), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ready")
    route_geometry: Mapped[object | None] = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)
    target_geometry: Mapped[object | None] = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    shape_similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_accuracy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    road_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    continuity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dead_end_penalty: Mapped[float | None] = mapped_column(Float, nullable=True)
    placement: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    debug: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    keypoint_geojson: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    job: Mapped[GenerationJob] = relationship(back_populates="candidates")


class GeneratedRoute(Base):
    __tablename__ = "generated_routes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("route_candidates.id"), nullable=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), nullable=False)
    artwork_id: Mapped[str] = mapped_column(ForeignKey("artworks.id"), nullable=False)
    artwork_name: Mapped[str] = mapped_column(Text, nullable=False)
    activity: Mapped[str] = mapped_column(Text, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_geometry: Mapped[object] = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    keypoint_geojson: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gpx_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RouteExport(Base):
    __tablename__ = "route_exports"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    route_id: Mapped[str] = mapped_column(ForeignKey("generated_routes.id", ondelete="CASCADE"), nullable=False)
    export_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShareLink(Base):
    __tablename__ = "share_links"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("generated_routes.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RoadGraphRow(Base):
    __tablename__ = "road_graphs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), nullable=False)
    activity: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox: Mapped[object] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
