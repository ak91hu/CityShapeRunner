"""Shared deterministic test configuration."""

from __future__ import annotations

import os

os.environ.setdefault("GEOCODE_OFFLINE", "1")
for secret_name in (
    "ORS_API_KEY",
    "OPENCODE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
):
    os.environ[secret_name] = ""
os.environ["OLLAMA_BASE_URL"] = ""
