"""Shared deterministic test configuration."""

from __future__ import annotations

import os

import pytest

os.environ["GEOCODE_OFFLINE"] = "1"  # force: never geocode live network during tests
for secret_name in (
    "ORS_API_KEY",
    "OPENCODE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
):
    os.environ[secret_name] = ""
os.environ["OLLAMA_BASE_URL"] = ""


@pytest.fixture(autouse=True)
def _clear_ors_memo_cache():
    """Keep memoised routing/scoring results from leaking between tests."""

    from gps_art_wizzard.tools import ors_client, shape_similarity

    ors_client.clear_directions_cache()
    shape_similarity._similarity_diagnostics_cached.cache_clear()
    yield
    ors_client.clear_directions_cache()
    shape_similarity._similarity_diagnostics_cached.cache_clear()
