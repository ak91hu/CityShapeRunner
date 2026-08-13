"""SVG/raster image-link import contracts."""

from __future__ import annotations

import socket

import httpx
import pytest

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
    assert imported.image_data_url is None
    assert imported.shape is not None
    assert imported.shape.source == "reference_svg"
    assert imported.shape.closed is True
    assert len(imported.shape.paths) == 2
    assert all(path[0] == path[-1] for path in imported.shape.paths)
    assert all(len(path) >= 13 for path in imported.shape.paths)


def test_webp_link_is_preserved_as_a_multimodal_reference(monkeypatch) -> None:
    _public_dns(monkeypatch)
    webp = b"RIFF\x04\x00\x00\x00WEBPVP8 "

    imported = image_reference.import_image_reference(
        "https://www.premiumsvg.com/wimg1/mug-icon.webp",
        client=_client(webp),
    )

    assert imported.kind == "raster"
    assert imported.name == "mug icon"
    assert imported.shape is None
    assert imported.image_data_url is not None
    assert imported.image_data_url.startswith("data:image/webp;base64,")


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

    with pytest.raises(image_reference.ImageReferenceError, match="direct SVG, PNG"):
        image_reference.import_image_reference(
            "https://example.com/not-an-image.svg",
            client=_client(b"<html>not an image</html>"),
        )
