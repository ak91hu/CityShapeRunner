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


@pytest.fixture(autouse=True)
def clear_gallery_list_cache():
    cloudinary_gallery._clear_gallery_list_cache()  # noqa: SLF001
    yield
    cloudinary_gallery._clear_gallery_list_cache()  # noqa: SLF001


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
    request_count = 0

    def fake_post(url, **kwargs):
        nonlocal request_count
        request_count += 1
        captured.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={
                "resources": [
                    {
                        "public_id": valid_id,
                        "secure_url": (
                            "https://res.cloudinary.com/test/image/upload/v1/map.png"
                        ),
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
    cached_result = cloudinary_gallery.list_gallery_images(limit=12)
    assert captured["json"]["expression"] == (
        "resource_type:image AND tags=gps-art-gallery"
    )
    assert request_count == 1
    assert cached_result == result
    assert result == {
        "configured": True,
        "assets": [
            {
                "id": valid_id,
                "image_url": (
                    "https://res.cloudinary.com/test/image/upload/v1/map.png"
                ),
                "thumbnail_url": (
                    "https://res.cloudinary.com/test/image/upload/"
                    "c_limit,f_auto,q_auto:good,w_720/v1/map.png"
                ),
                "preview_url": (
                    "https://res.cloudinary.com/test/image/upload/"
                    "c_limit,f_auto,q_auto:good,w_1600/v1/map.png"
                ),
                "width": 900,
                "height": 600,
                "campaign": None,
            }
        ],
        "next_cursor": "next-page",
    }


def test_gallery_campaign_slug_is_validated_inside_the_storage_boundary(
    cloudinary_env,
    monkeypatch,
):
    called = False

    def fake_post(*_args, **_kwargs):  # pragma: no cover - assertion guard
        nonlocal called
        called = True
        raise AssertionError("invalid campaign must not reach Cloudinary")

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", fake_post)
    with pytest.raises(cloudinary_gallery.GalleryImageError, match="Campaign"):
        cloudinary_gallery.list_gallery_images(campaign="bad OR tags=private")

    assert called is False


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


def test_gallery_listing_allows_short_lived_shared_caching(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/gallery")

    assert response.status_code == 200
    assert response.headers["cache-control"] == (
        "public, max-age=30, stale-while-revalidate=300"
    )


def test_gallery_api_publishes_without_forwarding_personal_fields(
    cloudinary_env,
    monkeypatch,
):
    public_id = "gps-art-gallery/" + ("b" * 32)
    seen = {}

    def fake_upload(image_data_url, publish_token, *, campaign=None):
        seen.update(image_data_url=image_data_url, publish_token=publish_token, campaign=campaign)
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
    assert set(seen) == {"image_data_url", "publish_token", "campaign"}
    assert seen["campaign"] is None


# ---- removal capability: token verification + delete endpoint ------------- #


def test_removal_token_binds_the_signature_to_one_public_id(cloudinary_env):
    config = cloudinary_gallery.get_cloudinary_config()
    public_id = "gps-art-gallery/" + ("d" * 32)
    token = cloudinary_gallery.removal_token(public_id, config)

    cloudinary_gallery.verify_removal_token(public_id, token, config)  # must not raise
    with pytest.raises(cloudinary_gallery.GalleryTokenError):
        cloudinary_gallery.verify_removal_token(public_id, "f" * 64, config)
    with pytest.raises(cloudinary_gallery.GalleryTokenError):
        # A valid token for a DIFFERENT asset must not authorise this one.
        other = cloudinary_gallery.removal_token(
            "gps-art-gallery/" + ("e" * 32), config
        )
        cloudinary_gallery.verify_removal_token(public_id, other, config)


def test_delete_gallery_image_sends_signed_destroy_request(cloudinary_env, monkeypatch):
    config = cloudinary_gallery.get_cloudinary_config()
    public_id = "gps-art-gallery/" + ("1" * 32)
    token = cloudinary_gallery.removal_token(public_id, config)
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"result": "ok"})

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", fake_post)
    removed = cloudinary_gallery.delete_gallery_image(public_id, token)

    assert removed is True
    assert captured["url"].endswith("/test-cloud/image/destroy")
    assert captured["data"]["public_id"] == public_id
    assert captured["data"]["invalidate"] == "true"
    assert captured["data"]["api_key"] == "test-key"
    assert "test-secret" not in captured["data"].values()
    assert captured["data"]["signature"]


def test_delete_gallery_image_accepts_not_found_and_rejects_other_results(
    cloudinary_env,
    monkeypatch,
):
    public_id = "gps-art-gallery/" + ("2" * 32)
    token = cloudinary_gallery.removal_token(
        public_id, cloudinary_gallery.get_cloudinary_config()
    )

    def responding(result):
        def fake_post(_url, **_kwargs):
            return httpx.Response(200, json={"result": result})

        return fake_post

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", responding("not found"))
    # An already-removed asset is not an error; it simply reports no removal.
    assert cloudinary_gallery.delete_gallery_image(public_id, token) is False

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", responding("deleted"))
    with pytest.raises(cloudinary_gallery.CloudinaryGalleryError):
        cloudinary_gallery.delete_gallery_image(public_id, token)

    def server_error(_url, **_kwargs):
        return httpx.Response(500, json={"error": {"message": "boom"}})

    monkeypatch.setattr(cloudinary_gallery.httpx, "post", server_error)
    with pytest.raises(cloudinary_gallery.CloudinaryGalleryError):
        cloudinary_gallery.delete_gallery_image(public_id, token)


def test_gallery_delete_endpoint_removes_with_a_valid_token(cloudinary_env, monkeypatch):
    public_id = "gps-art-gallery/" + ("3" * 32)
    seen = {}

    def fake_delete(public_id_arg, token_arg):
        seen.update(id=public_id_arg, token=token_arg)
        return True

    monkeypatch.setattr(
        gallery_api.cloudinary_gallery, "delete_gallery_image", fake_delete
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/gallery/delete",
            json={"public_id": public_id, "removal_token": "a" * 64},
        )

    assert response.status_code == 200
    assert response.json() == {"removed": True}
    assert seen == {"id": public_id, "token": "a" * 64}


def test_gallery_delete_endpoint_rejects_tampered_tokens_and_bad_ids(cloudinary_env):
    public_id = "gps-art-gallery/" + ("4" * 32)

    with TestClient(create_app()) as client:
        tampered = client.post(
            "/gallery/delete",
            json={"public_id": public_id, "removal_token": "b" * 64},
        )
        malformed = client.post(
            "/gallery/delete",
            json={"public_id": "gps-art-gallery/zzz", "removal_token": "c" * 64},
        )

    assert tampered.status_code == 403
    assert malformed.status_code == 422


def test_gallery_delete_endpoint_is_unavailable_without_configuration(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.post(
            "/gallery/delete",
            json={
                "public_id": "gps-art-gallery/" + ("5" * 32),
                "removal_token": "d" * 64,
            },
        )
    assert response.status_code == 503

