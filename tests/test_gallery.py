from __future__ import annotations

import base64
import struct
import zlib

import httpx
import pytest
from fastapi.testclient import TestClient

from gps_art_wizzard.api import gallery as gallery_api
from gps_art_wizzard.main import create_app
from gps_art_wizzard.tools import cloudinary_gallery


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _png_data_url(width: int = 320, height: int = 240, *, metadata: bool = False) -> str:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\x1b\x6b\x57" * width)
    chunks = [_png_chunk(b"IHDR", header)]
    if metadata:
        chunks.append(_png_chunk(b"tEXt", b"private-note\x00must-not-survive"))
    chunks.extend(
        [
            _png_chunk(b"IDAT", zlib.compress(row * height)),
            _png_chunk(b"IEND", b""),
        ]
    )
    raw = b"\x89PNG\r\n\x1a\n" + b"".join(chunks)
    return "data:image/png;base64," + base64.b64encode(raw).decode()


@pytest.fixture
def cloudinary_env(monkeypatch):
    monkeypatch.setenv(
        "CLOUDINARY_URL",
        "cloudinary://test-key:test-secret@test-cloud",
    )


def test_masked_cloudinary_secret_is_not_treated_as_configured(monkeypatch):
    monkeypatch.setenv(
        "CLOUDINARY_URL",
        "cloudinary://679635195647696:<paste_api_secret_here>@lflihp6z",
    )
    assert cloudinary_gallery.is_configured() is False
    with pytest.raises(cloudinary_gallery.GalleryConfigurationError):
        cloudinary_gallery.get_cloudinary_config()


def test_publish_token_rejects_tampering_and_expiry(cloudinary_env):
    token = cloudinary_gallery.maybe_issue_publish_token()
    assert token is not None
    public_id = cloudinary_gallery.verify_publish_token(token)
    assert public_id.startswith("gps-art-gallery/")

    with pytest.raises(cloudinary_gallery.GalleryTokenError):
        cloudinary_gallery.verify_publish_token(token + "tampered")
    with pytest.raises(cloudinary_gallery.GalleryTokenError, match="expired"):
        cloudinary_gallery.verify_publish_token(token, now=4_000_000_000)


def test_png_validation_strips_text_metadata():
    sanitised, width, height = cloudinary_gallery._strip_and_validate_png(  # noqa: SLF001
        _png_data_url(metadata=True)
    )
    assert (width, height) == (320, 240)
    assert b"private-note" not in sanitised
    assert b"tEXt" not in sanitised


def test_gallery_upload_is_signed_and_returns_stateless_removal_token(
    cloudinary_env,
    monkeypatch,
):
    token = cloudinary_gallery.maybe_issue_publish_token()
    public_id = cloudinary_gallery.verify_publish_token(token)
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={
                "public_id": public_id,
                "secure_url": "https://res.cloudinary.com/test/image/upload/map.png",
                "width": 320,
                "height": 240,
            },
        )

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", fake_post)
    result = cloudinary_gallery.upload_gallery_image(_png_data_url(), token)

    assert captured["url"].endswith("/test-cloud/image/upload")
    assert captured["data"]["api_key"] == "test-key"
    assert captured["data"]["public_id"] == public_id
    assert captured["data"]["tags"] == "gps-art-gallery"
    assert "test-secret" not in captured["data"].values()
    assert captured["files"]["file"][2] == "image/png"
    assert result["asset"]["id"] == public_id
    assert len(result["removal_token"]) == 64


def test_gallery_search_filters_non_gallery_resources(cloudinary_env, monkeypatch):
    valid_id = "gps-art-gallery/" + ("a" * 32)
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={
                "resources": [
                    {
                        "public_id": valid_id,
                        "secure_url": "https://res.cloudinary.com/test/map.png",
                        "width": 900,
                        "height": 600,
                    },
                    {
                        "public_id": "unrelated/private-image",
                        "secure_url": "https://res.cloudinary.com/test/private.png",
                    },
                ],
                "next_cursor": "next-page",
            },
        )

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", fake_post)
    result = cloudinary_gallery.list_gallery_images(limit=12)
    assert captured["json"]["expression"] == (
        "resource_type:image AND tags=gps-art-gallery"
    )
    assert result == {
        "configured": True,
        "assets": [
            {
                "id": valid_id,
                "image_url": "https://res.cloudinary.com/test/map.png",
                "width": 900,
                "height": 600,
            }
        ],
        "next_cursor": "next-page",
    }


def test_gallery_api_requires_public_location_consent(cloudinary_env):
    with TestClient(create_app()) as client:
        response = client.post(
            "/gallery",
            json={
                "image_data_url": _png_data_url(),
                "publish_token": "x" * 30,
                "confirm_public_location": False,
            },
        )
    assert response.status_code == 422


def test_gallery_api_publishes_without_forwarding_personal_fields(
    cloudinary_env,
    monkeypatch,
):
    public_id = "gps-art-gallery/" + ("b" * 32)
    seen = {}

    def fake_upload(image_data_url, publish_token):
        seen.update(image_data_url=image_data_url, publish_token=publish_token)
        return {
            "asset": {
                "id": public_id,
                "image_url": "https://res.cloudinary.com/test/map.png",
                "width": 320,
                "height": 240,
            },
            "removal_token": "c" * 64,
        }

    monkeypatch.setattr(
        gallery_api.cloudinary_gallery,
        "upload_gallery_image",
        fake_upload,
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/gallery",
            json={
                "image_data_url": _png_data_url(),
                "publish_token": "publish-capability-token-value",
                "confirm_public_location": True,
            },
        )
    assert response.status_code == 200
    assert response.json()["asset"]["id"] == public_id
    assert set(seen) == {"image_data_url", "publish_token"}

