"""Safely import a public SVG or raster image as a GPS-art reference."""

from __future__ import annotations

import base64
import ipaddress
import math
import re
import socket
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from svgelements import SVG, Close
from svgelements import Path as SvgPath
from svgelements import Shape as SvgShape

from ..state import Shape

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_SVG_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_SVG_SEGMENTS = 5_000
MAX_SVG_PATHS = 8
SUPPORTED_RASTER_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


class ImageReferenceError(ValueError):
    """A public image link could not be safely converted into route geometry."""


@dataclass(frozen=True)
class ImportedImageReference:
    name: str
    kind: str
    shape: Shape | None = None
    image_data_url: str | None = None


def import_image_reference(
    url: str,
    *,
    client: httpx.Client | None = None,
) -> ImportedImageReference:
    """Download and import one bounded public image URL.

    SVG geometry is sampled directly. PNG, JPEG, WebP and GIF files are
    returned as inline image data for the existing multimodal shape agent.
    """

    supplied_client = client is not None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={
            "Accept": "image/svg+xml,image/png,image/jpeg,image/webp,image/gif",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            ),
        },
    )
    try:
        content, final_url = _download_public_image(url, http_client)
    finally:
        if not supplied_client:
            http_client.close()

    media_type = _detect_media_type(content)
    name = _reference_name(final_url)
    if media_type == "image/svg+xml":
        return ImportedImageReference(
            name=name,
            kind="svg",
            shape=_shape_from_svg(content, name=name),
        )
    if media_type not in SUPPORTED_RASTER_TYPES:
        raise ImageReferenceError(
            "Use a direct SVG, PNG, JPG, WebP, or GIF image link."
        )
    encoded = base64.b64encode(content).decode("ascii")
    return ImportedImageReference(
        name=name,
        kind="raster",
        image_data_url=f"data:{media_type};base64,{encoded}",
    )


def _download_public_image(url: str, client: httpx.Client) -> tuple[bytes, str]:
    current_url = " ".join(str(url).split())
    for redirect_count in range(MAX_REDIRECTS + 1):
        _require_public_http_url(current_url)
        parsed_url = urlsplit(current_url)
        referer = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        try:
            with client.stream(
                "GET",
                current_url,
                follow_redirects=False,
                headers={"Referer": referer},
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirect_count >= MAX_REDIRECTS:
                        raise ImageReferenceError(
                            "The image link redirects too many times or has no destination."
                        )
                    current_url = urljoin(current_url, location)
                    continue
                if response.status_code != 200:
                    raise ImageReferenceError(
                        f"The image link could not be downloaded (HTTP {response.status_code})."
                    )
                declared_size = response.headers.get("content-length")
                if declared_size:
                    try:
                        if int(declared_size) > MAX_IMAGE_BYTES:
                            raise ImageReferenceError("The linked image must be 5 MB or smaller.")
                    except ValueError:
                        pass
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        raise ImageReferenceError("The linked image must be 5 MB or smaller.")
                    chunks.append(chunk)
                if not chunks:
                    raise ImageReferenceError("The image link returned an empty file.")
                return b"".join(chunks), current_url
        except ImageReferenceError:
            raise
        except httpx.HTTPError as exc:
            raise ImageReferenceError(
                "The image link could not be reached. Check that it is public and try again."
            ) from exc
    raise ImageReferenceError("The image link redirects too many times.")


def _require_public_http_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme.casefold() == "https" else 80)
    except ValueError as exc:
        raise ImageReferenceError("Enter a valid public image URL.") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ImageReferenceError("Enter a public HTTP or HTTPS image URL.")
    if parsed.username or parsed.password:
        raise ImageReferenceError("Image URLs containing credentials are not supported.")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        raise ImageReferenceError("The image link hostname could not be found.") from exc
    if not addresses:
        raise ImageReferenceError("The image link hostname could not be found.")
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise ImageReferenceError("The image link resolved to an invalid address.") from exc
        if not parsed_address.is_global:
            raise ImageReferenceError(
                "The image link must point to a public internet address."
            )


def _detect_media_type(content: bytes) -> str:
    prefix = content[:1_024].lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
    if b"<svg" in prefix:
        return "image/svg+xml"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _shape_from_svg(content: bytes, *, name: str) -> Shape:
    if len(content) > MAX_SVG_BYTES:
        raise ImageReferenceError("SVG files must be 2 MB or smaller.")
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ImageReferenceError("SVG files with document types or entities are not supported.")
    try:
        document = SVG.parse(BytesIO(content), reify=True, width=1_000, height=1_000)
    except Exception as exc:  # noqa: BLE001 - normalised to a safe public error
        raise ImageReferenceError("The linked SVG could not be parsed.") from exc

    candidates: list[tuple[float, list[tuple[float, float]], bool]] = []
    segment_count = 0
    try:
        for element in document.elements():
            if element is document or not isinstance(element, SvgShape):
                continue
            values = getattr(element, "values", {}) or {}
            if str(values.get("visibility", "")).casefold() == "hidden":
                continue
            if str(values.get("display", "")).casefold() == "none":
                continue
            path = SvgPath(element)
            path.reify()
            segment_count += len(path)
            if segment_count > MAX_SVG_SEGMENTS:
                raise ImageReferenceError("The linked SVG is too complex to turn into a route.")
            for subpath in path.as_subpaths():
                sampled_path = SvgPath(subpath)
                if len(sampled_path) < 2:
                    continue
                length = float(sampled_path.length(error=1e-3))
                if not math.isfinite(length) or length <= 0:
                    continue
                closed = isinstance(sampled_path[-1], Close)
                point_count = min(96, max(12, len(sampled_path) * 6))
                denominator = point_count if closed else point_count - 1
                points: list[tuple[float, float]] = []
                for index in range(point_count):
                    point = sampled_path.point(index / denominator, error=1e-3)
                    if point is None:
                        continue
                    x, y = float(point.x), -float(point.y)
                    if math.isfinite(x) and math.isfinite(y):
                        points.append((x, y))
                if closed and len(points) >= 3:
                    points.append(points[0])
                if len(points) >= 2:
                    candidates.append((length, points, closed))
    except ImageReferenceError:
        raise
    except Exception as exc:  # noqa: BLE001 - third-party parser error
        raise ImageReferenceError("The linked SVG contains unsupported geometry.") from exc

    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[:MAX_SVG_PATHS]
    if not selected:
        raise ImageReferenceError("The linked SVG contains no usable vector outline.")
    return Shape(
        name=name,
        paths=[points for _, points, _ in selected],
        closed=all(closed for _, _, closed in selected),
        source="reference_svg",
    )


def _reference_name(url: str) -> str:
    filename = unquote(PurePosixPath(urlsplit(url).path).name)
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    cleaned = re.sub(r"[^\w -]+", " ", stem, flags=re.UNICODE)
    cleaned = cleaned.replace("-", " ").replace("_", " ")
    cleaned = " ".join(cleaned.split())[:80]
    return cleaned or "imported image"
