"""Anonymous Cloudinary-backed map screenshot gallery.

Only rendered PNG images are persisted. Publish and removal capabilities are
stateless HMAC tokens so the application does not need a gallery database or
user accounts.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import struct
import time
import uuid
import zlib
from dataclasses import dataclass
from typing import TypedDict
from urllib.parse import quote, unquote, urlsplit

import httpx

_PUBLIC_ID_RE = re.compile(r"^gps-art-gallery/[a-f0-9]{32}$")
_PNG_PREFIX = "data:image/png;base64,"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_METADATA_CHUNKS = {b"eXIf", b"iTXt", b"tEXt", b"tIME", b"zTXt"}
_MAX_ENCODED_IMAGE_LENGTH = 8_000_000
_MAX_IMAGE_BYTES = 6_000_000
_MAX_IMAGE_DIMENSION = 4_096
_MAX_IMAGE_PIXELS = 16_000_000
_PUBLISH_TOKEN_TTL_SECONDS = 60 * 60


class GalleryConfigurationError(RuntimeError):
    """Raised when Cloudinary credentials are missing or incomplete."""


class GalleryTokenError(ValueError):
    """Raised when a publish or removal capability is invalid."""


class GalleryImageError(ValueError):
    """Raised when a submitted gallery image is unsafe or malformed."""


class CloudinaryGalleryError(RuntimeError):
    """Raised when Cloudinary cannot complete a gallery operation."""


@dataclass(frozen=True)
class CloudinaryConfig:
    cloud_name: str
    api_key: str
    api_secret: str


class GalleryAsset(TypedDict):
    id: str
    image_url: str
    width: int
    height: int


class GalleryUploadResult(TypedDict):
    asset: GalleryAsset
    removal_token: str


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return (
        not value
        or any(marker in value for marker in ("<", ">", "***"))
        or "your_api" in lowered
        or "paste_api" in lowered
    )


def get_cloudinary_config() -> CloudinaryConfig:
    """Parse ``CLOUDINARY_URL`` without ever logging or returning the raw URL."""

    raw = os.getenv("CLOUDINARY_URL", "").strip()
    if not raw:
        raise GalleryConfigurationError("Cloudinary gallery storage is not configured.")
    parsed = urlsplit(raw)
    cloud_name = unquote(parsed.hostname or "").strip()
    api_key = unquote(parsed.username or "").strip()
    api_secret = unquote(parsed.password or "").strip()
    if parsed.scheme != "cloudinary" or any(
        _looks_like_placeholder(value)
        for value in (cloud_name, api_key, api_secret)
    ):
        raise GalleryConfigurationError(
            "Cloudinary gallery storage has an incomplete CLOUDINARY_URL."
        )
    return CloudinaryConfig(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
    )


def is_configured() -> bool:
    try:
        get_cloudinary_config()
    except GalleryConfigurationError:
        return False
    return True


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise GalleryTokenError("The gallery publish token is malformed.") from exc


def _token_signature(body: str, config: CloudinaryConfig) -> str:
    return _urlsafe_encode(
        hmac.new(
            config.api_secret.encode("utf-8"),
            b"gps-art-gallery-publish:" + body.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )


def maybe_issue_publish_token() -> str | None:
    """Return a short-lived, single-public-ID capability when configured."""

    try:
        config = get_cloudinary_config()
    except GalleryConfigurationError:
        return None
    payload = {
        "v": 1,
        "id": uuid.uuid4().hex,
        "exp": int(time.time()) + _PUBLISH_TOKEN_TTL_SECONDS,
    }
    body = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{body}.{_token_signature(body, config)}"


def verify_publish_token(
    token: str,
    *,
    config: CloudinaryConfig | None = None,
    now: int | None = None,
) -> str:
    """Validate a publish capability and return its fixed Cloudinary public ID."""

    cfg = config or get_cloudinary_config()
    try:
        body, supplied_signature = token.split(".", 1)
    except ValueError as exc:
        raise GalleryTokenError("The gallery publish token is malformed.") from exc
    expected_signature = _token_signature(body, cfg)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise GalleryTokenError("The gallery publish token is invalid.")
    try:
        payload = json.loads(_urlsafe_decode(body))
        identifier = str(payload["id"])
        expires_at = int(payload["exp"])
        version = int(payload["v"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GalleryTokenError("The gallery publish token is malformed.") from exc
    current_time = int(time.time()) if now is None else now
    if version != 1 or expires_at < current_time:
        raise GalleryTokenError("The gallery publish token has expired.")
    public_id = f"gps-art-gallery/{identifier}"
    if not _PUBLIC_ID_RE.fullmatch(public_id):
        raise GalleryTokenError("The gallery publish token is malformed.")
    return public_id


def removal_token(public_id: str, config: CloudinaryConfig) -> str:
    if not _PUBLIC_ID_RE.fullmatch(public_id):
        raise GalleryTokenError("The gallery asset identifier is invalid.")
    return hmac.new(
        config.api_secret.encode("utf-8"),
        f"gps-art-gallery-remove:{public_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_removal_token(
    public_id: str,
    supplied_token: str,
    config: CloudinaryConfig,
) -> None:
    expected = removal_token(public_id, config)
    if not hmac.compare_digest(supplied_token, expected):
        raise GalleryTokenError("The gallery removal token is invalid.")


def _strip_and_validate_png(image_data_url: str) -> tuple[bytes, int, int]:
    """Decode a PNG, reject hidden trailing data, and remove metadata chunks."""

    if len(image_data_url) > _MAX_ENCODED_IMAGE_LENGTH:
        raise GalleryImageError("The gallery screenshot is too large.")
    if not image_data_url.startswith(_PNG_PREFIX):
        raise GalleryImageError("The gallery screenshot must be a PNG data URL.")
    try:
        raw = base64.b64decode(
            image_data_url[len(_PNG_PREFIX) :],
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise GalleryImageError("The gallery screenshot contains invalid PNG data.") from exc
    if len(raw) > _MAX_IMAGE_BYTES:
        raise GalleryImageError("The gallery screenshot is too large.")
    if not raw.startswith(_PNG_SIGNATURE):
        raise GalleryImageError("The gallery screenshot is not a valid PNG.")

    output = bytearray(_PNG_SIGNATURE)
    offset = len(_PNG_SIGNATURE)
    width = height = 0
    saw_header = saw_image_data = saw_end = False
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(raw):
            raise GalleryImageError("The gallery screenshot has a truncated PNG chunk.")
        chunk_type = raw[offset + 4 : offset + 8]
        chunk_data = raw[offset + 8 : offset + 8 + length]
        supplied_crc = struct.unpack(">I", raw[offset + 8 + length : chunk_end])[0]
        expected_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if supplied_crc != expected_crc:
            raise GalleryImageError("The gallery screenshot has a damaged PNG chunk.")

        if chunk_type == b"IHDR":
            if saw_header or length != 13 or offset != len(_PNG_SIGNATURE):
                raise GalleryImageError("The gallery screenshot has an invalid PNG header.")
            width, height = struct.unpack(">II", chunk_data[:8])
            saw_header = True
        elif chunk_type == b"IDAT":
            saw_image_data = True
        elif chunk_type == b"IEND":
            if length != 0:
                raise GalleryImageError("The gallery screenshot has an invalid PNG ending.")
            saw_end = True

        if chunk_type not in _PNG_METADATA_CHUNKS:
            output.extend(raw[offset:chunk_end])
        offset = chunk_end
        if chunk_type == b"IEND":
            break

    if not (saw_header and saw_image_data and saw_end) or offset != len(raw):
        raise GalleryImageError("The gallery screenshot is incomplete or has hidden data.")
    if (
        width < 240
        or height < 180
        or width > _MAX_IMAGE_DIMENSION
        or height > _MAX_IMAGE_DIMENSION
        or width * height > _MAX_IMAGE_PIXELS
    ):
        raise GalleryImageError("The gallery screenshot dimensions are not allowed.")
    return bytes(output), width, height


def _cloudinary_signature(params: dict[str, object], api_secret: str) -> str:
    serialised = "&".join(
        f"{key}={params[key]}"
        for key in sorted(params)
        if params[key] is not None and params[key] != ""
    )
    return hashlib.sha1(  # noqa: S324 - Cloudinary's signing protocol requires SHA-1.
        f"{serialised}{api_secret}".encode()
    ).hexdigest()


def _api_base(config: CloudinaryConfig) -> str:
    return f"https://api.cloudinary.com/v1_1/{quote(config.cloud_name, safe='')}"


def _cloudinary_error(response: httpx.Response, operation: str) -> CloudinaryGalleryError:
    try:
        message = str(response.json().get("error", {}).get("message", "")).strip()
    except (AttributeError, ValueError):
        message = ""
    suffix = f" ({message[:160]})" if message else ""
    return CloudinaryGalleryError(f"Cloudinary could not {operation}{suffix}.")


def _public_asset(resource: dict) -> GalleryAsset | None:
    public_id = str(resource.get("public_id", ""))
    secure_url = str(resource.get("secure_url", ""))
    if not _PUBLIC_ID_RE.fullmatch(public_id) or not secure_url.startswith("https://"):
        return None
    return {
        "id": public_id,
        "image_url": secure_url,
        "width": int(resource.get("width") or 0),
        "height": int(resource.get("height") or 0),
    }


def upload_gallery_image(
    image_data_url: str,
    publish_token: str,
) -> GalleryUploadResult:
    config = get_cloudinary_config()
    public_id = verify_publish_token(publish_token, config=config)
    png, width, height = _strip_and_validate_png(image_data_url)
    timestamp = int(time.time())
    signed_params: dict[str, object] = {
        "overwrite": "false",
        "public_id": public_id,
        "tags": "gps-art-gallery",
        "timestamp": timestamp,
    }
    form = {
        **signed_params,
        "api_key": config.api_key,
        "signature": _cloudinary_signature(signed_params, config.api_secret),
    }
    try:
        response = httpx.post(
            f"{_api_base(config)}/image/upload",
            data=form,
            files={"file": ("gps-art-map.png", png, "image/png")},
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
    except httpx.HTTPError as exc:
        raise CloudinaryGalleryError("Cloudinary could not upload the gallery image.") from exc
    if response.status_code >= 400:
        raise _cloudinary_error(response, "upload the gallery image")
    try:
        resource = response.json()
    except ValueError as exc:
        raise CloudinaryGalleryError("Cloudinary returned an invalid upload response.") from exc
    asset = _public_asset(resource)
    if asset is None or asset["id"] != public_id:
        raise CloudinaryGalleryError("Cloudinary returned an unexpected gallery asset.")
    # Dimensions from the sanitised source remain authoritative if a mock or
    # provider response omits them.
    asset["width"] = int(asset["width"] or width)
    asset["height"] = int(asset["height"] or height)
    return {
        "asset": asset,
        "removal_token": removal_token(public_id, config),
    }


def list_gallery_images(*, limit: int = 24, cursor: str | None = None) -> dict:
    config = get_cloudinary_config()
    query: dict[str, object] = {
        "expression": "resource_type:image AND tags=gps-art-gallery",
        "sort_by": [{"created_at": "desc"}],
        "max_results": limit,
    }
    if cursor:
        query["next_cursor"] = cursor
    try:
        response = httpx.post(
            f"{_api_base(config)}/resources/search",
            auth=(config.api_key, config.api_secret),
            json=query,
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
    except httpx.HTTPError as exc:
        raise CloudinaryGalleryError("Cloudinary could not load the gallery.") from exc
    if response.status_code >= 400:
        raise _cloudinary_error(response, "load the gallery")
    try:
        payload = response.json()
    except ValueError as exc:
        raise CloudinaryGalleryError("Cloudinary returned an invalid gallery response.") from exc
    assets = [
        asset
        for resource in payload.get("resources", [])
        if (asset := _public_asset(resource)) is not None
    ]
    next_cursor = payload.get("next_cursor")
    return {
        "configured": True,
        "assets": assets,
        "next_cursor": str(next_cursor) if next_cursor else None,
    }


def delete_gallery_image(public_id: str, supplied_removal_token: str) -> bool:
    config = get_cloudinary_config()
    verify_removal_token(public_id, supplied_removal_token, config)
    timestamp = int(time.time())
    signed_params: dict[str, object] = {
        "invalidate": "true",
        "public_id": public_id,
        "timestamp": timestamp,
    }
    form = {
        **signed_params,
        "api_key": config.api_key,
        "signature": _cloudinary_signature(signed_params, config.api_secret),
    }
    try:
        response = httpx.post(
            f"{_api_base(config)}/image/destroy",
            data=form,
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
    except httpx.HTTPError as exc:
        raise CloudinaryGalleryError("Cloudinary could not remove the gallery image.") from exc
    if response.status_code >= 400:
        raise _cloudinary_error(response, "remove the gallery image")
    try:
        result = str(response.json().get("result", ""))
    except (AttributeError, ValueError) as exc:
        raise CloudinaryGalleryError("Cloudinary returned an invalid removal response.") from exc
    if result not in {"ok", "not found"}:
        raise CloudinaryGalleryError("Cloudinary did not confirm gallery image removal.")
    return result == "ok"
