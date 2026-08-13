"""SVG/raster image-link import contracts."""

from __future__ import annotations

import base64
import socket
from io import BytesIO

import httpx
import pytest
from PIL import Image

from gps_art_wizzard.tools import image_reference


def _public_dns(monkeypatch) -> None:
    monkeypatch.setattr(
        image_reference.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )


def _client(content: bytes, *, status: int = 200) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status, content=content)
        )
    )


def _raster(format_name: str, *, size: tuple[int, int] = (48, 32)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (20, 80, 160)).save(output, format=format_name)
    return output.getvalue()


def test_svg_link_becomes_sampled_route_geometry(monkeypatch) -> None:
    _public_dns(monkeypatch)
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <path d="M10 70 C10 25 65 15 75 45 L92 45 L92 68 L75 68 C65 92 10 95 10 70 Z"/>
      <circle cx="80" cy="56" r="8"/>
    </svg>"""

    imported = image_reference.import_image_reference(
        "https://example.com/mug.svg",
        client=_client(svg),
    )

    assert imported.kind == "svg"
    assert imported.name == "mug"
    assert imported.image_data_url is not None
    assert imported.image_data_url.startswith("data:image/png;base64,")
    assert imported.shape is not None
    assert imported.shape.source == "reference_svg"
    assert imported.shape.closed is True
    assert len(imported.shape.paths) == 2
    assert all(path[0] == path[-1] for path in imported.shape.paths)
    assert all(len(path) >= 13 for path in imported.shape.paths)


def test_webp_link_is_preserved_as_a_multimodal_reference(monkeypatch) -> None:
    _public_dns(monkeypatch)
    webp = _raster("WEBP")

    imported = image_reference.import_image_reference(
        "https://www.premiumsvg.com/wimg1/mug-icon.webp",
        client=_client(webp),
    )

    assert imported.kind == "raster"
    assert imported.name == "mug icon"
    assert imported.shape is None
    assert imported.image_data_url is not None
    assert imported.image_data_url.startswith("data:image/png;base64,")


@pytest.mark.parametrize("format_name", ["BMP", "TIFF", "GIF", "PNG", "JPEG"])
def test_pillow_decodable_raster_formats_are_normalised_for_ai(
    monkeypatch,
    format_name: str,
) -> None:
    _public_dns(monkeypatch)

    imported = image_reference.import_image_reference(
        f"https://example.com/drawing.{format_name.casefold()}",
        client=_client(_raster(format_name, size=(1_600, 800))),
    )

    assert imported.kind == "raster"
    assert imported.image_data_url is not None
    encoded = imported.image_data_url.split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as normalised:
        assert normalised.format == "PNG"
        assert normalised.mode == "RGB"
        assert max(normalised.size) == image_reference.REFERENCE_IMAGE_MAX_DIMENSION


def test_image_import_rejects_private_network_destinations(monkeypatch) -> None:
    monkeypatch.setattr(
        image_reference.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ],
    )
    client = _client(b"<svg/>")

    with pytest.raises(image_reference.ImageReferenceError, match="public internet address"):
        image_reference.import_image_reference(
            "http://localhost/internal.svg",
            client=client,
        )


def test_image_import_rejects_html_disguised_as_an_image(monkeypatch) -> None:
    _public_dns(monkeypatch)

    with pytest.raises(image_reference.ImageReferenceError, match="valid raster image"):
        image_reference.import_image_reference(
            "https://example.com/not-an-image.svg",
            client=_client(b"<html>not an image</html>"),
        )


def test_repeated_public_url_reuses_the_normalised_image(monkeypatch) -> None:
    image_reference._import_public_image_cached.cache_clear()  # noqa: SLF001
    calls = 0

    def download(_url, _client):
        nonlocal calls
        calls += 1
        return _raster("PNG"), "https://example.com/drawing.png"

    monkeypatch.setattr(image_reference, "_download_public_image", download)
    try:
        first = image_reference.import_image_reference(
            " https://example.com/drawing.png "
        )
        second = image_reference.import_image_reference(
            "https://example.com/drawing.png"
        )
    finally:
        image_reference._import_public_image_cached.cache_clear()  # noqa: SLF001

    assert calls == 1
    assert first == second
    assert first is not second
