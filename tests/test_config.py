"""Unit tests for environment parsing and YAML configuration precedence."""

from __future__ import annotations

import pytest

from gps_art_wizzard import config


@pytest.fixture(autouse=True)
def clear_settings_cache():
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on"])
def test_bool_accepts_documented_true_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("TEST_BOOLEAN", value)

    assert config._bool("TEST_BOOLEAN", False) is True  # noqa: SLF001


@pytest.mark.parametrize("value", ["0", "false", "FALSE", " no ", "off"])
def test_bool_accepts_documented_false_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("TEST_BOOLEAN", value)

    assert config._bool("TEST_BOOLEAN", True) is False  # noqa: SLF001


def test_bool_uses_default_for_missing_or_unknown_values(monkeypatch) -> None:
    monkeypatch.delenv("TEST_BOOLEAN", raising=False)
    assert config._bool("TEST_BOOLEAN", True) is True  # noqa: SLF001

    monkeypatch.setenv("TEST_BOOLEAN", "sometimes")
    assert config._bool("TEST_BOOLEAN", False) is False  # noqa: SLF001


def test_split_env_trims_values_and_removes_empty_entries(monkeypatch) -> None:
    monkeypatch.setenv("TEST_FALLBACKS", " openai, , anthropic,ollama ")

    assert config._split_env("TEST_FALLBACKS", ["default"]) == [  # noqa: SLF001
        "openai",
        "anthropic",
        "ollama",
    ]


def test_yaml_overlays_populate_workflow_and_routing(monkeypatch) -> None:
    for name in (
        "MAX_REFINEMENT_ITERATIONS",
        "PREFLIGHT_ENABLED",
        "ORS_SNAP_RADIUS_M",
        "ORS_CONTINUE_STRAIGHT",
        "DEFAULT_RUN_DISTANCE_KM",
        "DEFAULT_BIKE_DISTANCE_KM",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        config,
        "_load_yaml_overlays",
        lambda: {
            "workflow": {
                "max_refinement_iterations": 9,
                "preflight_enabled": False,
                "distance_bounds": {"run": [5, 25], "bike": [15, 120]},
                "distance_defaults": {"run": 7.5, "bike": 24.0},
            },
            "routing": {
                "snap_radius_m": 250,
                "continue_straight": True,
                "preference": "shortest",
            },
        },
    )

    settings = config.get_settings()

    assert settings.workflow.max_refinement_iterations == 9
    assert settings.workflow.preflight_enabled is False
    assert settings.workflow.distance_bounds == {"run": [5, 25], "bike": [15, 120]}
    assert settings.workflow.distance_defaults == {"run": 7.5, "bike": 24.0}
    assert settings.routing.snap_radius_m == 250
    assert settings.routing.continue_straight is True
    assert settings.routing.preference == "shortest"


def test_environment_values_override_yaml_overlays(monkeypatch) -> None:
    monkeypatch.setenv("MAX_REFINEMENT_ITERATIONS", "4")
    monkeypatch.setenv("PREFLIGHT_ENABLED", "false")
    monkeypatch.setenv("ORS_SNAP_RADIUS_M", "90")
    monkeypatch.setenv("ORS_CONTINUE_STRAIGHT", "false")
    monkeypatch.setenv("DEFAULT_RUN_DISTANCE_KM", "6.5")
    monkeypatch.setattr(
        config,
        "_load_yaml_overlays",
        lambda: {
            "workflow": {
                "max_refinement_iterations": 11,
                "preflight_enabled": True,
                "distance_defaults": {"run": 8.0, "bike": 22.0},
            },
            "routing": {"snap_radius_m": 300, "continue_straight": True},
        },
    )

    settings = config.get_settings()

    assert settings.workflow.max_refinement_iterations == 4
    assert settings.workflow.preflight_enabled is False
    assert settings.workflow.distance_defaults == {"run": 6.5, "bike": 22.0}
    assert settings.routing.snap_radius_m == 90
    assert settings.routing.continue_straight is False


def test_routing_uses_the_current_heigit_public_endpoint_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ORS_BASE_URL", raising=False)

    assert config.RoutingConfig().ors_base_url == "https://api.heigit.org/openrouteservice"


def test_settings_are_cached_until_explicitly_cleared(monkeypatch) -> None:
    monkeypatch.setattr(config, "_load_yaml_overlays", lambda: {})
    monkeypatch.setenv("DEFAULT_CITY", "Budapest")
    first = config.get_settings()

    monkeypatch.setenv("DEFAULT_CITY", "Szeged")
    assert config.get_settings() is first
    assert config.get_settings().workflow.city_default == "Budapest"

    config.get_settings.cache_clear()
    assert config.get_settings().workflow.city_default == "Szeged"
