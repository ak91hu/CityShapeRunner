"""Image-only anonymous gallery HTTP endpoints."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..tools import cloudinary_gallery

router = APIRouter(tags=["gallery"])
log = logging.getLogger(__name__)
_PUBLIC_ID_RE = re.compile(r"^gps-art-gallery/[a-f0-9]{32}$")


class GalleryPublishRequest(BaseModel):
    image_data_url: str = Field(..., min_length=100, max_length=8_000_000)
    publish_token: str = Field(..., min_length=20, max_length=500)
    confirm_public_location: bool

    @field_validator("confirm_public_location")
    @classmethod
    def require_public_location_confirmation(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("publishing requires confirmation that the mapped location is public")
        return value


class GalleryDeleteRequest(BaseModel):
    public_id: str = Field(..., min_length=40, max_length=80)
    removal_token: str = Field(..., min_length=64, max_length=64)

    @field_validator("public_id")
    @classmethod
    def validate_public_id(cls, value: str) -> str:
        if not _PUBLIC_ID_RE.fullmatch(value):
            raise ValueError("invalid gallery asset identifier")
        return value


def _gallery_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, cloudinary_gallery.GalleryConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, cloudinary_gallery.GalleryTokenError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, cloudinary_gallery.GalleryImageError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(
        status_code=502,
        detail="The anonymous map gallery is temporarily unavailable.",
    )


@router.get("/gallery")
def get_gallery(
    limit: int = Query(default=24, ge=1, le=50),
    cursor: str | None = Query(default=None, min_length=1, max_length=500),
) -> dict:
    if not cloudinary_gallery.is_configured():
        return {"configured": False, "assets": [], "next_cursor": None}
    try:
        return cloudinary_gallery.list_gallery_images(limit=limit, cursor=cursor)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Anonymous gallery listing failed",
            extra={"event": "gallery.list.failed"},
        )
        raise _gallery_http_error(exc) from exc


@router.post("/gallery")
def publish_gallery_image(
    req: GalleryPublishRequest,
) -> cloudinary_gallery.GalleryUploadResult:
    try:
        result = cloudinary_gallery.upload_gallery_image(
            req.image_data_url,
            req.publish_token,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Anonymous gallery publication failed",
            extra={"event": "gallery.publish.failed"},
        )
        raise _gallery_http_error(exc) from exc
    asset = result["asset"]
    log.info(
        "Anonymous map screenshot published",
        extra={
            "event": "gallery.publish.completed",
            "gallery_id": asset["id"],
        },
    )
    return result


@router.post("/gallery/delete")
def remove_gallery_image(req: GalleryDeleteRequest) -> dict:
    try:
        removed = cloudinary_gallery.delete_gallery_image(
            req.public_id,
            req.removal_token,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Anonymous gallery removal failed",
            extra={"event": "gallery.remove.failed", "gallery_id": req.public_id},
        )
        raise _gallery_http_error(exc) from exc
    log.info(
        "Anonymous map screenshot removed",
        extra={
            "event": "gallery.remove.completed",
            "gallery_id": req.public_id,
        },
    )
    return {"removed": removed}
