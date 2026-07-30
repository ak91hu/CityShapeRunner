"""Prompt templates + loader. See ``prompts/*.txt`` and ``registry.render``."""

from .registry import get, render

__all__ = ["get", "render"]
