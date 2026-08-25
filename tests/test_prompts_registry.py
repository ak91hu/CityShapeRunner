"""Tests for the prompt template registry (loading + token substitution)."""

from __future__ import annotations

import pytest

from gps_art_wizzard.prompts import registry


@pytest.fixture
def template_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "PROMPT_DIR", tmp_path)
    registry.get.cache_clear()  # noqa: SLF001
    yield tmp_path
    registry.get.cache_clear()  # noqa: SLF001


def test_render_substitutes_known_tokens_and_format_specs(template_dir):
    (template_dir / "greeting.txt").write_text(
        "Hello {who}, target {distance:.1f} km!\n{json_example}",
        encoding="utf-8",
    )

    rendered = registry.render(
        "greeting",
        who="runner",
        distance=8.25,
        json_example='{"keep": "me"}',
    )

    assert rendered == 'Hello runner, target 8.2 km!\n{"keep": "me"}'


def test_render_leaves_unknown_tokens_and_literal_braces_untouched(template_dir):
    (template_dir / "strict.txt").write_text(
        "{known} and {unknown_token} and {not_even_a_token}",
        encoding="utf-8",
    )

    rendered = registry.render("strict", known="kept")

    assert rendered == "kept and {unknown_token} and {not_even_a_token}"


def test_render_survives_an_invalid_format_spec(template_dir):
    (template_dir / "odd.txt").write_text("{value:>notaspec}", encoding="utf-8")

    # format() raises ValueError for the bogus spec; render must fall back.
    assert registry.render("odd", value=7) == "7"


def test_get_raises_a_clear_error_for_missing_templates(template_dir):
    with pytest.raises(FileNotFoundError, match="missing_template"):
        registry.get("missing_template")


def test_get_is_cached_until_cleared(template_dir):
    path = template_dir / "cached.txt"
    path.write_text("first", encoding="utf-8")
    assert registry.get("cached") == "first"

    path.write_text("second", encoding="utf-8")
    assert registry.get("cached") == "first"  # served from cache

    registry.get.cache_clear()  # noqa: SLF001
    assert registry.get("cached") == "second"
